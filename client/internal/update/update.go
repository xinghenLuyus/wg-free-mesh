package update

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"

	"wfm/client/internal/bind"
	"wfm/client/internal/profile"
	"wfm/client/internal/service"
)

func ParseArgs(args []string) (bool, string, error) {
	local := false
	selector := ""
	serverSeen := false
	for _, arg := range args {
		if arg == "--server" {
			if serverSeen {
				return false, "", fmt.Errorf("duplicate --server")
			}
			local = true
			serverSeen = true
			continue
		}
		if strings.HasPrefix(arg, "--server=") {
			if serverSeen || selector != "" {
				return false, "", fmt.Errorf("duplicate binding selector")
			}
			local = true
			serverSeen = true
			selector = strings.TrimPrefix(arg, "--server=")
			if selector == "" {
				return false, "", fmt.Errorf("empty binding selector")
			}
			continue
		}
		if strings.HasPrefix(arg, "-") || selector != "" {
			return false, "", fmt.Errorf("usage: wfmctl update [--server] [profile_id_or_number]")
		}
		selector = arg
	}
	if selector == "" {
		selector = "1"
	}
	return local, selector, nil
}

func selectProfile(selector string) (profile.Profile, error) {
	items, _, err := profile.Summaries()
	if err != nil {
		return profile.Profile{}, err
	}
	for _, item := range items {
		if item.ProfileID == selector {
			return profile.Load(item.ProfileID)
		}
	}
	index, err := strconv.Atoi(selector)
	if err != nil || index < 1 || index > len(items) {
		return profile.Profile{}, fmt.Errorf("binding %q not found; use wfmctl list", selector)
	}
	return profile.Load(items[index-1].ProfileID)
}

func realFile(path string) (string, error) {
	if !filepath.IsAbs(path) {
		return "", fmt.Errorf("installation path must be absolute")
	}
	return filepath.EvalSymlinks(path)
}

func installedPaths(state service.UpdateState) (string, string, error) {
	agent, err := realFile(state.Binary)
	if err != nil {
		return "", "", err
	}
	ctl := filepath.Join(filepath.Dir(agent), "wfmctl"+suffix())
	ctl, err = realFile(ctl)
	if err != nil {
		return "", "", err
	}
	current, err := os.Executable()
	if err != nil {
		return "", "", err
	}
	current, err = realFile(current)
	if err != nil {
		return "", "", err
	}
	if !samePath(current, ctl) {
		return "", "", fmt.Errorf("this wfmctl is not the installed service's companion; run %s update instead", ctl)
	}
	return ctl, agent, nil
}

func samePath(a, b string) bool {
	if runtime.GOOS == "windows" {
		return strings.EqualFold(filepath.Clean(a), filepath.Clean(b))
	}
	return filepath.Clean(a) == filepath.Clean(b)
}

func checkInstallWritable(paths ...string) error {
	seen := map[string]bool{}
	for _, path := range paths {
		dir := filepath.Dir(path)
		if seen[dir] {
			continue
		}
		seen[dir] = true
		file, err := os.CreateTemp(dir, ".wfm-update-check-*")
		if err != nil {
			return fmt.Errorf("installation directory is not writable: %w", err)
		}
		name := file.Name()
		closeErr := file.Close()
		removeErr := os.Remove(name)
		if closeErr != nil {
			return closeErr
		}
		if removeErr != nil {
			return removeErr
		}
	}
	return nil
}

func Run(args []string) (err error) {
	local, selector, err := ParseArgs(args)
	if err != nil {
		return err
	}
	state, err := service.CheckUpdate()
	if err != nil {
		return err
	}
	ctl, agent, err := installedPaths(state)
	if err != nil {
		return err
	}
	dir := filepath.Join(service.UpdateRoot(), "active")
	if _, statErr := os.Stat(dir); statErr == nil {
		old, readErr := loadJob(dir)
		if _, lockErr := os.Stat(filepath.Join(dir, "applying")); lockErr == nil || readErr != nil || (old.Phase != "complete" && old.Phase != "failed") {
			return fmt.Errorf("unfinished update exists; inspect %s/state.json and result.log; nothing was overwritten", dir)
		}
		if old.Phase == "failed" {
			fmt.Printf("Previous update failed; inspect %s\n", filepath.Join(dir, "result.log"))
		}
	} else if !os.IsNotExist(statErr) {
		return statErr
	}
	p, err := selectProfile(selector)
	if err != nil {
		return err
	}
	request := map[string]string{"config_id": p.Profile.ConfigID, "node_id": p.Profile.NodeID, "goos": runtime.GOOS, "goarch": runtime.GOARCH}
	info, err := serverRequest(p, "check", request)
	if err != nil {
		return err
	}
	if info.GOOS != runtime.GOOS || info.GOARCH != runtime.GOARCH {
		return fmt.Errorf("server target platform mismatch")
	}
	needsUpdate := false
	for _, item := range []struct{ path, program string }{{ctl, "ctl"}, {agent, "agent"}} {
		version, err := binaryVersion(item.path, item.program, runtime.GOOS, runtime.GOARCH)
		if err != nil {
			return err
		}
		comparison, err := CompareVersions(info.Version, version)
		if err != nil {
			return err
		}
		if comparison < 0 {
			return fmt.Errorf("refusing downgrade: %s is %s, server is %s", item.program, version, info.Version)
		}
		if comparison > 0 {
			needsUpdate = true
		}
	}
	if comparison, err := CompareVersions(info.Version, bind.Version); err != nil || comparison < 0 {
		return fmt.Errorf("current CLI version cannot be upgraded to server version %q", info.Version)
	}
	source := "github_release"
	if local {
		source = "local_build"
	}
	fmt.Printf("Binding: %s (%s/%s)\nServer: %s\nTarget: %s %s/%s\nSource: %s\n", p.Profile.ProfileID, p.Profile.ConfigName, p.Profile.NodeName, p.Profile.ServerURL, info.Version, runtime.GOOS, runtime.GOARCH, source)
	if !needsUpdate {
		fmt.Println("Already at the server version; no changes.")
		return nil
	}
	if err = checkInstallWritable(ctl, agent); err != nil {
		return err
	}
	if err = service.SecureUpdateRoot(); err != nil {
		return err
	}
	lockPath := filepath.Join(service.UpdateRoot(), "lock")
	if err = os.Mkdir(lockPath, 0o700); err != nil {
		return fmt.Errorf("another update owns the lock or was interrupted; inspect %s: %w", service.UpdateRoot(), err)
	}
	handedOff := false
	defer func() {
		if !handedOff {
			_ = os.Remove(lockPath)
		}
	}()
	if _, statErr := os.Stat(dir); statErr == nil {
		if _, lockErr := os.Stat(filepath.Join(dir, "applying")); lockErr == nil {
			return fmt.Errorf("an update helper is active or was interrupted; inspect %s", dir)
		}
		old, readErr := loadJob(dir)
		if readErr != nil || (old.Phase != "complete" && old.Phase != "failed") {
			return fmt.Errorf("unfinished update exists at %s; inspect state.json and result.log before retrying; nothing was overwritten", dir)
		}
		if err = profile.AtomicJSON(filepath.Join(service.UpdateRoot(), "last-result.json"), old); err != nil {
			return err
		}
		if err = os.RemoveAll(dir); err != nil {
			return err
		}
	} else if !os.IsNotExist(statErr) {
		return statErr
	}
	if err = os.Mkdir(dir, 0o700); err != nil {
		return fmt.Errorf("another update owns the update directory: %w", err)
	}
	defer func() {
		if !handedOff {
			if cleanupErr := os.RemoveAll(dir); cleanupErr != nil && err == nil {
				err = cleanupErr
			}
		}
	}()
	request["version"] = info.Version
	request["source"] = source
	artifact, err := serverRequest(p, "artifact", request)
	if err != nil {
		return err
	}
	if artifact.Version != info.Version {
		return fmt.Errorf("server version changed during update; retry")
	}
	manifest, err := obtainPackage(p, artifact, dir, local)
	if err != nil {
		return err
	}
	// Recheck both installed files after a potentially long download/build.
	job := job{Phase: "ready", Version: info.Version, ParentPID: os.Getpid(), Ctl: ctl, Agent: agent, Hashes: manifest.Files, ProfileID: p.Profile.ProfileID, Source: source}
	job.OriginalCtlHash, err = fileHash(ctl)
	if err != nil {
		return err
	}
	job.OriginalAgentHash, err = fileHash(agent)
	if err != nil {
		return err
	}
	for _, item := range []struct{ path, program string }{{ctl, "ctl"}, {agent, "agent"}} {
		current, err := binaryVersion(item.path, item.program, runtime.GOOS, runtime.GOARCH)
		if err != nil {
			return err
		}
		if comparison, err := CompareVersions(job.Version, current); err != nil || comparison < 0 {
			return fmt.Errorf("installed version changed; refusing to continue")
		}
	}
	if err = copyFile(ctl, filepath.Join(dir, "previous-ctl"+suffix()), 0o700); err != nil {
		return err
	}
	if err = copyFile(agent, filepath.Join(dir, "previous-agent"+suffix()), 0o700); err != nil {
		return err
	}
	if err = saveJob(dir, job); err != nil {
		return err
	}
	log, err := os.OpenFile(filepath.Join(dir, "result.log"), os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o600)
	if err != nil {
		return err
	}
	defer log.Close()
	helper := exec.Command(filepath.Join(dir, "wfmctl"+suffix()), "__update-apply")
	helper.Stdout = log
	helper.Stderr = log
	helper.Dir = dir
	helper.Env = service.UpdateHelperEnvironment()
	service.DetachUpdate(helper)
	if err = helper.Start(); err != nil {
		return err
	}
	handedOff = true
	_ = helper.Process.Release()
	fmt.Printf("Update handed to the privileged helper, not completed yet.\nResult: %s\n", filepath.Join(dir, "result.log"))
	return nil
}
