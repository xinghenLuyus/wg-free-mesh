package mqtt

import (
	"context"
	"crypto/sha256"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"sync"
	"time"

	"wfm/client/internal/profile"
)

var lifecycleLocks sync.Map
var regexpUtun = regexp.MustCompile(`^utun[0-9]+$`)
var readTool = toolOutput

func bindingLock(p profile.Profile) *sync.Mutex {
	lock, _ := lifecycleLocks.LoadOrStore(p.Profile.ProfileID, &sync.Mutex{})
	return lock.(*sync.Mutex)
}

type transition struct {
	Phase        string              `json:"phase"`
	WasRunning   bool                `json:"was_running"`
	Next         profile.ProfileMeta `json:"next_profile"`
	Names        map[string]string   `json:"interface_names"`
	TargetSHA256 string              `json:"target_sha256"`
}

func toolOutput(protocol string, args ...string) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	body, err := exec.CommandContext(ctx, tunnelTool(protocol), args...).CombinedOutput()
	if ctx.Err() != nil {
		return "", ctx.Err()
	}
	if err != nil {
		return "", fmt.Errorf("%s query failed: %w: %s", tunnelTool(protocol), err, strings.TrimSpace(string(body)))
	}
	return strings.TrimSpace(string(body)), nil
}

func mappedInterface(name, protocol string) (string, error) {
	if runtime.GOOS != "darwin" {
		return name, nil
	}
	if filepath.Base(name) != name || strings.ContainsAny(name, "/\\") {
		return "", fmt.Errorf("invalid interface name")
	}
	dir := "/var/run/wireguard"
	if protocol == "amneziawg_2" {
		dir = "/var/run/amneziawg"
	}
	body, err := os.ReadFile(filepath.Join(dir, name+".name"))
	if os.IsNotExist(err) {
		return "", nil
	}
	if err != nil {
		return "", err
	}
	actual := strings.TrimSpace(string(body))
	if !regexpUtun.MatchString(actual) {
		return "", fmt.Errorf("invalid macOS interface mapping for %s", name)
	}
	return actual, nil
}

// queryInterface distinguishes a genuinely absent device from command/permission failures.
func queryInterface(name, protocol string) (string, string, error) {
	actual, err := mappedInterface(name, protocol)
	if err != nil || actual == "" {
		return "", "", err
	}
	return queryDevice(actual, protocol)
}

func queryDevice(actual, protocol string) (string, string, error) {
	interfaces, err := readTool(protocol, "show", "interfaces")
	if err != nil {
		return "", "", err
	}
	for _, item := range strings.Fields(interfaces) {
		if item != actual {
			continue
		}
		key, err := readTool(protocol, "show", actual, "public-key")
		if err != nil {
			return "", "", err
		}
		if key == "" || key == "(none)" {
			return "", "", fmt.Errorf("interface %s has no public key", actual)
		}
		return actual, key, nil
	}
	return "", "", nil
}

func candidates(p profile.Profile) ([]profile.Bundle, error) {
	bundles, err := profile.Bundles(p)
	if err != nil {
		return nil, err
	}
	legacy, err := profile.LegacyBundles(p)
	return append(bundles, legacy...), err
}

func (s *Session) tunnelStatus() (bool, error) {
	bundles, err := candidates(s.profile)
	if err != nil {
		return false, err
	}
	if len(bundles) == 0 {
		return false, nil
	}
	running, err := ownedRunning(s.profile)
	return len(running) > 0, err
}

func ownedRunning(p profile.Profile) ([]profile.Bundle, error) {
	bundles, err := candidates(p)
	if err != nil {
		return nil, err
	}
	seen := map[string]bool{}
	live := map[string]bool{}
	var running []profile.Bundle
	for _, candidate := range bundles {
		m := candidate.Manifest
		identity := m.Protocol + "/" + m.InterfaceName
		if seen[identity] {
			continue
		}
		seen[identity] = true
		actual, key, err := queryInterface(m.InterfaceName, m.Protocol)
		if err != nil {
			return nil, err
		}
		if actual == "" {
			continue
		}
		matched := false
		for _, b := range bundles {
			if b.Manifest.Protocol == m.Protocol && b.Manifest.InterfaceName == m.InterfaceName && b.Manifest.PublicKey == key {
				if !live[m.Protocol+"/"+actual] {
					running = append(running, b)
				}
				live[m.Protocol+"/"+actual] = true
				matched = true
				break
			}
		}
		if !matched {
			return nil, fmt.Errorf("interface %s ownership mismatch; refusing to stop it", actual)
		}
	}
	if runtime.GOOS == "darwin" {
		checked := map[string]bool{}
		for _, b := range bundles {
			protocol := b.Manifest.Protocol
			if checked[protocol] {
				continue
			}
			checked[protocol] = true
			if _, err = exec.LookPath(tunnelTool(protocol)); errors.Is(err, exec.ErrNotFound) {
				continue
			}
			interfaces, err := toolOutput(protocol, "show", "interfaces")
			if err != nil {
				return nil, err
			}
			for _, device := range strings.Fields(interfaces) {
				if live[protocol+"/"+device] {
					continue
				}
				key, err := toolOutput(protocol, "show", device, "public-key")
				if err != nil {
					return nil, err
				}
				for _, candidate := range bundles {
					if candidate.Manifest.Protocol == protocol && candidate.Manifest.PublicKey == key {
						return nil, fmt.Errorf("owned interface %s is running but its name mapping is missing; preserve configs and repair the mapping before retrying", device)
					}
				}
			}
		}
	}
	return running, nil
}

func stopOwned(p profile.Profile) (bool, error) {
	running, err := ownedRunning(p)
	if err != nil {
		return false, err
	}
	for _, b := range running {
		m := b.Manifest
		actual, key, err := queryInterface(m.InterfaceName, m.Protocol)
		if err != nil {
			return true, err
		}
		if actual == "" {
			continue
		}
		if key != m.PublicKey {
			return true, fmt.Errorf("interface ownership changed before stop")
		}
		stopConfig, err := os.ReadFile(b.StopPath())
		if err != nil {
			return true, err
		}
		if fmt.Sprintf("%x", sha256.Sum256(stopConfig)) != m.SHA256 {
			return true, fmt.Errorf("stop configuration changed; refusing to run mismatched hooks")
		}
		if err = stopWireGuard(m.InterfaceName, b.StopPath(), m.Protocol); err != nil {
			return true, err
		}
		if err = waitDeviceStopped(actual, m.Protocol, 15*time.Second); err != nil {
			return true, err
		}
	}
	// Recheck all generations; do not retire the only evidence for a surviving interface.
	remaining, err := ownedRunning(p)
	if err != nil {
		return len(running) > 0, err
	}
	if len(remaining) > 0 {
		return true, fmt.Errorf("owned interfaces remain after stop")
	}
	return len(running) > 0, nil
}

func waitDeviceStopped(actual, protocol string, timeout time.Duration) error {
	deadline := time.Now().Add(timeout)
	for {
		device, _, err := queryDevice(actual, protocol)
		if err != nil {
			return err
		}
		if device == "" {
			return nil
		}
		if time.Now().After(deadline) {
			return fmt.Errorf("interface %s did not stop before timeout", actual)
		}
		time.Sleep(250 * time.Millisecond)
	}
}

func currentBundle(p profile.Profile) (profile.Bundle, error) {
	dir, err := profile.Directory(p)
	if err != nil {
		return profile.Bundle{}, err
	}
	return profile.ReadBundle(filepath.Join(dir, "config"), p)
}

func startBundle(b profile.Bundle) error {
	m := b.Manifest
	if err := startWireGuard(m.InterfaceName, b.ConfigPath(), m.Protocol); err != nil {
		return err
	}
	deadline := time.Now().Add(15 * time.Second)
	for {
		actual, key, err := queryInterface(m.InterfaceName, m.Protocol)
		if err != nil {
			return err
		}
		if actual != "" {
			if key != m.PublicKey {
				return fmt.Errorf("started interface ownership mismatch")
			}
			return nil
		}
		if time.Now().After(deadline) {
			return fmt.Errorf("new interface did not become ready")
		}
		time.Sleep(250 * time.Millisecond)
	}
}

func preflightBundle(b profile.Bundle) error {
	activationTool := tunnelQuickTool(b.Manifest.Protocol)
	if runtime.GOOS == "windows" {
		activationTool = tunnelServiceTool(b.Manifest.Protocol)
	}
	for _, tool := range []string{tunnelTool(b.Manifest.Protocol), activationTool} {
		if _, err := exec.LookPath(tool); err != nil {
			return err
		}
	}
	if runtime.GOOS != "windows" {
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		// strip parses the quick configuration without running hooks or creating an interface.
		// Do not include its output in errors: successful output contains the private key.
		if err := exec.CommandContext(ctx, activationTool, "strip", b.ConfigPath()).Run(); err != nil {
			return fmt.Errorf("configuration preflight failed: %w", err)
		}
	}
	return nil
}

func readTransition(dir string) (*transition, error) {
	body, err := os.ReadFile(filepath.Join(dir, "transition.json"))
	if os.IsNotExist(err) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	var t transition
	if err = json.Unmarshal(body, &t); err != nil {
		return nil, err
	}
	return &t, nil
}

func removeTransition(dir string) error {
	err := os.Remove(filepath.Join(dir, "transition.json"))
	if os.IsNotExist(err) {
		return nil
	}
	return err
}

func moveGeneration(dir, from, to string) error {
	_, err := os.Stat(filepath.Join(dir, from))
	if os.IsNotExist(err) {
		return nil
	}
	if err != nil {
		return err
	}
	if _, err = os.Stat(filepath.Join(dir, to)); err == nil {
		return fmt.Errorf("generation destination %s already exists", to)
	} else if !os.IsNotExist(err) {
		return err
	}
	return os.Rename(filepath.Join(dir, from), filepath.Join(dir, to))
}

// resumeTransition is idempotent at each filesystem boundary. A recorded start failure
// is not retried automatically, since arbitrary user hooks are not transactional.
func (s *Session) resumeTransition(manual bool) error {
	dir, err := profile.Directory(s.profile)
	if err != nil {
		return err
	}
	t, err := readTransition(dir)
	if err != nil || t == nil {
		return err
	}
	if t.Next.ProfileID != s.profile.Profile.ProfileID || t.Next.ConfigID != s.profile.Profile.ConfigID || t.Next.NodeID != s.profile.Profile.NodeID {
		return fmt.Errorf("transition binding mismatch")
	}
	save := func(phase string) error {
		t.Phase = phase
		return profile.AtomicJSON(filepath.Join(dir, "transition.json"), t)
	}
	for {
		switch t.Phase {
		case "prepared":
			next := s.profile
			next.Profile = t.Next
			next.InterfaceNames = t.Names
			pending, err := profile.ReadBundle(filepath.Join(dir, ".config.pending"), next)
			if err != nil {
				return err
			}
			if pending.Manifest.SHA256 != t.TargetSHA256 || pending.Manifest.ServerName != t.Next.InterfaceName {
				return fmt.Errorf("pending configuration does not match transition")
			}
			if err = preflightBundle(pending); err != nil {
				return err
			}
			// A crash can occur after down but before its confirmation is recorded.
			if _, err = stopOwned(s.profile); err != nil {
				return err
			}
			if err = save("stopped"); err != nil {
				return err
			}
		case "stopped":
			next := s.profile
			next.Profile = t.Next
			next.InterfaceNames = t.Names
			pending, err := profile.ReadBundle(filepath.Join(dir, ".config.pending"), next)
			if err != nil {
				return err
			}
			if pending.Manifest.SHA256 != t.TargetSHA256 || pending.Manifest.ServerName != t.Next.InterfaceName {
				return fmt.Errorf("pending configuration changed after stop")
			}
			if err = os.RemoveAll(filepath.Join(dir, "config.old2")); err != nil {
				return err
			}
			if err = save("old2_removed"); err != nil {
				return err
			}
		case "old2_removed":
			if err = moveGeneration(dir, "config.old", "config.old2"); err != nil {
				return err
			}
			if err = save("old_moved"); err != nil {
				return err
			}
		case "old_moved":
			if err = moveGeneration(dir, "config", "config.old"); err != nil {
				return err
			}
			if err = save("current_moved"); err != nil {
				return err
			}
		case "current_moved":
			if err = moveGeneration(dir, ".config.pending", "config"); err != nil {
				return err
			}
			if err = save("installed"); err != nil {
				return err
			}
		case "installed", "starting", "failed":
			next := s.profile
			next.Profile = t.Next
			next.InterfaceNames = t.Names
			b, err := currentBundle(next)
			if err != nil {
				return err
			}
			if b.Manifest.SHA256 != t.TargetSHA256 || b.Manifest.ServerName != t.Next.InterfaceName {
				return fmt.Errorf("installed configuration does not match transition")
			}
			if err = profile.SaveMetadata(next); err != nil {
				return err
			}
			s.profile = next
			if t.Phase == "failed" {
				if !manual {
					return fmt.Errorf("previous configuration start failed; use start or push_config to retry")
				}
				return removeTransition(dir)
			}
			if t.WasRunning {
				if err = save("starting"); err != nil {
					return err
				}
				// Reconcile a process death immediately after up before trying again.
				running, err := ownedRunning(next)
				if err != nil {
					return err
				}
				ready := len(running) == 1 && running[0].Manifest.InterfaceName == b.Manifest.InterfaceName && running[0].Manifest.Protocol == b.Manifest.Protocol && running[0].Manifest.PublicKey == b.Manifest.PublicKey
				if !ready {
					if _, err = stopOwned(next); err != nil {
						return err
					}
					if err = startBundle(b); err != nil {
						if saveErr := save("failed"); saveErr != nil {
							return fmt.Errorf("start failed: %v; record failure: %w", err, saveErr)
						}
						return fmt.Errorf("new configuration start failed: %w", err)
					}
				}
			}
			return removeTransition(dir)
		default:
			return fmt.Errorf("unknown transition phase %q", t.Phase)
		}
	}
}

func (s *Session) replaceConfiguration(payload map[string]any) error {
	dir, err := profile.Directory(s.profile)
	if err != nil {
		return err
	}
	previous, err := readTransition(dir)
	if err != nil {
		return err
	}
	restoreRunning := previous != nil && previous.WasRunning
	// A fresh push can replace a failed preparation without requiring its broken
	// pending configuration/toolchain to become usable first. No rotation has begun.
	if previous == nil || (previous.Phase != "prepared" && previous.Phase != "failed") {
		if err := s.resumeTransition(true); err != nil {
			return err
		}
	}
	if err := profile.Migrate(s.profile); err != nil {
		return err
	}
	text := payloadString(payload, "config_text")
	if text == "" {
		return fmt.Errorf("config_text is required")
	}
	next := s.profile
	if name := payloadString(payload, "interface_name"); name != "" {
		next.Profile.InterfaceName = name
	}
	next, err = profile.ResolveInterfaceName(next)
	if err != nil {
		return err
	}
	m, err := profile.NewManifest(next, text, tunnelProtocolFromPayload(payload), payloadString(payload, "config_version"), payloadString(payload, "awg_version"))
	if err != nil {
		return err
	}
	if hash := payloadString(payload, "config_sha256"); hash != "" && hash != m.SHA256 {
		return fmt.Errorf("configuration hash mismatch")
	}
	dir, err = profile.Directory(next)
	if err != nil {
		return err
	}
	current, err := currentBundle(s.profile)
	if err != nil && !os.IsNotExist(err) {
		return err
	}
	if err == nil && (previous == nil || previous.Phase != "prepared") && current.Manifest.SHA256 == m.SHA256 && current.Manifest.InterfaceName == m.InterfaceName && current.Manifest.ServerName == m.ServerName && current.Manifest.Protocol == m.Protocol && current.Manifest.AWGVersion == m.AWGVersion {
		if previous != nil && previous.Phase == "failed" {
			if restoreRunning {
				return s.controlConfiguration("start")
			}
			return s.controlConfiguration("stop")
		}
		return nil
	}
	pending := profile.Bundle{Manifest: m, Dir: filepath.Join(dir, ".config.pending")}
	// Only a prepared (not yet rotated) transaction may be superseded here. Its
	// target hash prevents recovery from applying a partially overwritten pending bundle.
	if err = os.RemoveAll(pending.Dir); err != nil {
		return err
	}
	if err = profile.WriteBundle(pending.Dir, m, text); err != nil {
		return err
	}
	if err = preflightBundle(pending); err != nil {
		return err
	}
	running, err := ownedRunning(s.profile)
	if err != nil {
		return err
	}
	actual, _, err := queryInterface(m.InterfaceName, m.Protocol)
	if err != nil {
		return err
	}
	if actual != "" {
		owned := false
		for _, b := range running {
			if b.Manifest.InterfaceName == m.InterfaceName && b.Manifest.Protocol == m.Protocol {
				owned = true
				break
			}
		}
		if !owned {
			return fmt.Errorf("target interface name is already in use outside this binding")
		}
	}
	t := transition{Phase: "prepared", WasRunning: len(running) > 0 || restoreRunning, Next: next.Profile, Names: next.InterfaceNames, TargetSHA256: m.SHA256}
	if err = profile.AtomicJSON(filepath.Join(dir, "transition.json"), t); err != nil {
		return err
	}
	return s.resumeTransition(false)
}

func payloadString(payload map[string]any, key string) string {
	value := fmt.Sprint(payload[key])
	if value == "<nil>" {
		return ""
	}
	return value
}

func (s *Session) controlConfiguration(action string) (result error) {
	dir, err := profile.Directory(s.profile)
	if err != nil {
		return err
	}
	prior, err := readTransition(dir)
	if err != nil {
		return err
	}
	if prior != nil && prior.Phase == "failed" {
		defer func() {
			if result != nil {
				if err := profile.AtomicJSON(filepath.Join(dir, "transition.json"), prior); err != nil {
					result = fmt.Errorf("%v; preserve failure record: %w", result, err)
				}
			}
		}()
	}
	if action == "stop" {
		if prior != nil {
			prior.WasRunning = false
			if err = profile.AtomicJSON(filepath.Join(dir, "transition.json"), prior); err != nil {
				return err
			}
			if prior.Phase == "prepared" {
				if _, err = stopOwned(s.profile); err != nil {
					return err
				}
				return removeTransition(dir)
			}
		}
	}
	if err := s.resumeTransition(true); err != nil {
		return err
	}
	if err := profile.Migrate(s.profile); err != nil {
		return err
	}
	if action == "stop" {
		_, err := stopOwned(s.profile)
		return err
	}
	if action != "start" {
		return fmt.Errorf("unsupported control action: %s", action)
	}
	b, err := currentBundle(s.profile)
	if err != nil {
		return err
	}
	if err = preflightBundle(b); err != nil {
		return err
	}
	running, err := ownedRunning(s.profile)
	if err != nil {
		return err
	}
	if len(running) == 1 && running[0].Manifest.InterfaceName == b.Manifest.InterfaceName && running[0].Manifest.Protocol == b.Manifest.Protocol && running[0].Manifest.PublicKey == b.Manifest.PublicKey {
		return nil
	}
	if _, err = stopOwned(s.profile); err != nil {
		return err
	}
	return startBundle(b)
}
