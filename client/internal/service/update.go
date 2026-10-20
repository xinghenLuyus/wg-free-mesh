package service

import (
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

type UpdateState struct {
	Binary  string `json:"binary"`
	Running bool   `json:"running"`
	PID     int    `json:"pid"`
	State   string `json:"state"`
}

func CheckUpdate() (UpdateState, error) {
	if err := requireBindPrivileges(); err != nil {
		return UpdateState{}, err
	}
	state, err := updateStatus()
	if err == nil && state.State != "running" && state.State != "stopped" {
		err = fmt.Errorf("service is changing state; retry later")
	}
	if err == nil && state.Running && state.PID <= 0 {
		err = fmt.Errorf("cannot identify running agent process")
	}
	return state, err
}

func UpdateStatus() (UpdateState, error) { return updateStatus() }
func UpdateProcessAlive(pid int) (bool, error) {
	if pid <= 0 {
		return false, nil
	}
	return updateProcessAlive(pid)
}

func StopForUpdate(original UpdateState) error {
	if err := requestUpdateStop(); err != nil {
		return err
	}
	deadline := time.Now().Add(30 * time.Second)
	for {
		state, err := updateStatus()
		if err != nil {
			return err
		}
		alive, err := UpdateProcessAlive(original.PID)
		if err != nil {
			return err
		}
		if state.State == "stopped" && state.PID == 0 && !alive {
			return nil
		}
		if time.Now().After(deadline) {
			return fmt.Errorf("agent did not fully stop within 30 seconds")
		}
		time.Sleep(250 * time.Millisecond)
	}
}

func StartAfterUpdate() error {
	if err := Start(); err != nil {
		return err
	}
	deadline := time.Now().Add(30 * time.Second)
	stable := time.Time{}
	lastPID := 0
	for {
		state, err := updateStatus()
		if err != nil {
			return err
		}
		if state.Running && state.PID > 0 {
			if lastPID != state.PID {
				stable = time.Time{}
				lastPID = state.PID
			}
			if stable.IsZero() {
				stable = time.Now()
			}
			if time.Since(stable) >= 3*time.Second {
				return nil
			}
		} else {
			stable = time.Time{}
		}
		if time.Now().After(deadline) {
			return fmt.Errorf("agent did not become stably running within 30 seconds")
		}
		time.Sleep(250 * time.Millisecond)
	}
}

func UpdateRoot() string {
	if runtime.GOOS == "windows" {
		return filepath.Join(programDataForUpdate(), "wg-free-mesh", "update")
	}
	if runtime.GOOS == "darwin" {
		return "/Library/Application Support/WG Free Mesh/update"
	}
	return "/var/lib/wg-free-mesh/update"
}

func programDataForUpdate() string {
	if base := os.Getenv("ProgramData"); base != "" {
		return base
	}
	return `C:\ProgramData`
}

func SecureUpdateRoot() error {
	if err := os.MkdirAll(UpdateRoot(), 0o700); err != nil {
		return err
	}
	info, err := os.Lstat(UpdateRoot())
	if err != nil {
		return err
	}
	if !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		return fmt.Errorf("update directory must not be a link")
	}
	return secureUpdateRoot(UpdateRoot())
}

// Mirror the standard tool locations used by the installed Unix service; this
// changes only the helper's environment, never machine-wide PATH settings.
func UpdateHelperEnvironment() []string {
	env := os.Environ()
	if runtime.GOOS == "windows" {
		return env
	}
	prefix := "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
	if runtime.GOOS == "darwin" {
		prefix = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
	}
	result := make([]string, 0, len(env)+1)
	for _, value := range env {
		if !strings.HasPrefix(value, "PATH=") {
			result = append(result, value)
		}
	}
	return append(result, "PATH="+prefix+":"+os.Getenv("PATH"))
}
