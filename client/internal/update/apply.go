package update

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"time"

	"wfm/client/internal/mqtt"
	"wfm/client/internal/profile"
	"wfm/client/internal/service"
)

type job struct {
	Phase             string              `json:"phase"`
	Version           string              `json:"version"`
	ParentPID         int                 `json:"parent_pid"`
	Ctl               string              `json:"ctl"`
	Agent             string              `json:"agent"`
	Hashes            map[string]string   `json:"hashes"`
	OriginalCtlHash   string              `json:"original_ctl_hash"`
	OriginalAgentHash string              `json:"original_agent_hash"`
	Original          service.UpdateState `json:"original_service"`
	Tunnels           []mqtt.UpdateTunnel `json:"tunnels"`
	Error             string              `json:"error,omitempty"`
	Activated         bool                `json:"activated"`
	ProfileID         string              `json:"profile_id"`
	Source            string              `json:"source"`
}

func saveJob(dir string, j job) error { return profile.AtomicJSON(filepath.Join(dir, "state.json"), j) }
func loadJob(dir string) (job, error) {
	var j job
	body, err := os.ReadFile(filepath.Join(dir, "state.json"))
	if err != nil {
		return j, err
	}
	err = json.Unmarshal(body, &j)
	return j, err
}

func copyFile(from, to string, mode os.FileMode) error {
	source, err := os.Open(from)
	if err != nil {
		return err
	}
	defer source.Close()
	target, err := os.OpenFile(to, os.O_CREATE|os.O_EXCL|os.O_WRONLY, mode)
	if err != nil {
		return err
	}
	_, err = io.Copy(target, source)
	if err == nil {
		err = target.Sync()
	}
	closeErr := target.Close()
	if err != nil {
		return err
	}
	return closeErr
}

func replaceFile(from, to string) error {
	temp, err := os.CreateTemp(filepath.Dir(to), ".wfm-update-*")
	if err != nil {
		return err
	}
	name := temp.Name()
	defer os.Remove(name)
	source, err := os.Open(from)
	if err != nil {
		temp.Close()
		return err
	}
	_, err = io.Copy(temp, source)
	source.Close()
	if err == nil {
		err = temp.Chmod(0o755)
	}
	if err == nil {
		err = temp.Sync()
	}
	closeErr := temp.Close()
	if err != nil {
		return err
	}
	if closeErr != nil {
		return closeErr
	}
	return replacePlatform(name, to)
}

func restoreBinary(backup, target, expectedHash string) error {
	if current, err := fileHash(target); err == nil && current == expectedHash {
		return nil
	}
	return replaceFile(backup, target)
}

func RunHelper() (result error) {
	if _, err := service.CheckUpdate(); err != nil {
		return err
	}
	dir := filepath.Join(service.UpdateRoot(), "active")
	j, err := loadJob(dir)
	if err != nil {
		return err
	}
	if j.Phase != "ready" {
		return fmt.Errorf("update helper will not repeat phase %q; inspect %s", j.Phase, dir)
	}
	executable, err := os.Executable()
	if err != nil {
		return err
	}
	if !samePath(executable, filepath.Join(dir, "wfmctl"+suffix())) {
		return fmt.Errorf("update helper must run from the protected staging directory")
	}
	if err = os.Mkdir(filepath.Join(dir, "applying"), 0o700); err != nil {
		return fmt.Errorf("another helper is active or requires recovery: %w", err)
	}
	lockPath := filepath.Join(service.UpdateRoot(), "lock")
	lockInfo, err := os.Lstat(lockPath)
	if err != nil || !lockInfo.IsDir() || lockInfo.Mode()&os.ModeSymlink != 0 {
		_ = os.Remove(filepath.Join(dir, "applying"))
		return fmt.Errorf("update handoff lock is missing or invalid")
	}
	defer func() { _ = os.Remove(filepath.Join(dir, "applying")); _ = os.Remove(lockPath) }()
	for _, item := range []struct{ path, name, program string }{{j.Ctl, "wfmctl" + suffix(), "ctl"}, {j.Agent, "wfm-agent" + suffix(), "agent"}} {
		if !filepath.IsAbs(item.path) {
			return fmt.Errorf("invalid update destination")
		}
		hash, err := fileHash(filepath.Join(dir, item.name))
		if err != nil || hash != j.Hashes[item.name] {
			return fmt.Errorf("staged binary checksum mismatch")
		}
		version, err := binaryVersion(filepath.Join(dir, item.name), item.program, runtime.GOOS, runtime.GOARCH)
		if err != nil || version != j.Version {
			return fmt.Errorf("staged binary version mismatch")
		}
	}
	deadline := time.Now().Add(30 * time.Second)
	for {
		alive, err := service.UpdateProcessAlive(j.ParentPID)
		if err != nil {
			return err
		}
		if !alive {
			break
		}
		if time.Now().After(deadline) {
			return fmt.Errorf("original CLI did not exit; no files replaced")
		}
		time.Sleep(100 * time.Millisecond)
	}
	stopped := false
	replaced := false
	activated := false
	defer func() {
		if result != nil {
			if stopped && !activated {
				state, statusErr := service.UpdateStatus()
				if statusErr != nil || state.State != "stopped" || state.PID != 0 {
					j.Phase = "recovery_required"
					j.Error = fmt.Sprintf("%v; cannot confirm stopped service for recovery: %v", result, statusErr)
					_ = saveJob(dir, j)
					result = fmt.Errorf("%s; inspect %s", j.Error, dir)
					return
				}
				if replaced {
					ctlErr := restoreBinary(filepath.Join(dir, "previous-ctl"+suffix()), j.Ctl, j.OriginalCtlHash)
					agentErr := restoreBinary(filepath.Join(dir, "previous-agent"+suffix()), j.Agent, j.OriginalAgentHash)
					if ctlErr != nil || agentErr != nil {
						j.Phase = "recovery_required"
						j.Error = fmt.Sprintf("%v; restore binaries: ctl=%v agent=%v", result, ctlErr, agentErr)
						_ = saveJob(dir, j)
						result = fmt.Errorf("%s; inspect %s", j.Error, dir)
						return
					}
				}
				if err := mqtt.RestoreUpdateTunnels(j.Tunnels); err != nil {
					result = fmt.Errorf("%v; tunnel recovery: %w", result, err)
				}
				if j.Original.Running {
					if err := service.StartAfterUpdate(); err != nil {
						result = fmt.Errorf("%v; service recovery: %w", result, err)
					}
				}
			}
			j.Phase = "failed"
			j.Error = result.Error()
			if err := saveJob(dir, j); err != nil {
				result = fmt.Errorf("%v; record result: %w", result, err)
			}
			fmt.Fprintf(os.Stderr, "Update failed: %v\n", result)
		}
	}()
	state, err := service.CheckUpdate()
	if err != nil {
		return err
	}
	agent, err := realFile(state.Binary)
	if err != nil || !samePath(agent, j.Agent) {
		return fmt.Errorf("installed service path changed")
	}
	for _, item := range []struct{ path, hash, backup string }{{j.Ctl, j.OriginalCtlHash, "previous-ctl" + suffix()}, {j.Agent, j.OriginalAgentHash, "previous-agent" + suffix()}} {
		hash, err := fileHash(item.path)
		if err != nil || hash != item.hash {
			return fmt.Errorf("installed program changed during download")
		}
		backupHash, err := fileHash(filepath.Join(dir, item.backup))
		if err != nil || backupHash != item.hash {
			return fmt.Errorf("previous binary backup is incomplete")
		}
	}
	j.Original = state
	j.Tunnels, err = mqtt.CaptureUpdateTunnels()
	if err != nil {
		return err
	}
	j.Phase = "stopping"
	if err = saveJob(dir, j); err != nil {
		return err
	}
	// Even a failed stop request may have stopped the service: preserve recovery intent.
	stopped = true
	if err = service.StopForUpdate(state); err != nil {
		return err
	}
	j.Phase = "replacing"
	if err = saveJob(dir, j); err != nil {
		return err
	}
	replaced = true
	if err = replaceFile(filepath.Join(dir, "wfmctl"+suffix()), j.Ctl); err != nil {
		return err
	}
	if err = replaceFile(filepath.Join(dir, "wfm-agent"+suffix()), j.Agent); err != nil {
		return err
	}
	for _, item := range []struct{ path, name string }{{j.Ctl, "wfmctl" + suffix()}, {j.Agent, "wfm-agent" + suffix()}} {
		hash, err := fileHash(item.path)
		if err != nil || hash != j.Hashes[item.name] {
			return fmt.Errorf("installed binary verification failed")
		}
	}
	j.Phase = "activating"
	j.Activated = true
	if err = saveJob(dir, j); err != nil {
		return err
	}
	activated = true
	restoreErr := mqtt.RestoreUpdateTunnels(j.Tunnels)
	if state.Running {
		if err = service.StartAfterUpdate(); err != nil {
			return err
		}
	} else {
		current, err := service.UpdateStatus()
		if err != nil {
			return err
		}
		if current.State != "stopped" || current.PID != 0 {
			return fmt.Errorf("previously stopped service unexpectedly started")
		}
	}
	if restoreErr != nil {
		return fmt.Errorf("binaries updated, tunnel recovery failed: %w", restoreErr)
	}
	j.Phase = "complete"
	if err = saveJob(dir, j); err != nil {
		return err
	}
	fmt.Printf("Update complete: %s. Previous service and tunnel states restored.\n", j.Version)
	return nil
}
