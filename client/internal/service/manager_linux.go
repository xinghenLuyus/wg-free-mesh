package service

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

const systemdUnit = `/etc/systemd/system/wfm-agent.service`

func Install() error {
	if err := requireRoot(); err != nil {
		return err
	}
	agentPath, err := agentPath()
	if err != nil {
		return err
	}
	unit := fmt.Sprintf(`[Unit]
Description=WG Free Mesh Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=%s
Restart=on-failure
RestartSec=3
User=root
WorkingDirectory=/var/lib/wg-free-mesh

[Install]
WantedBy=multi-user.target
`, agentPath)
	if err := os.MkdirAll("/var/lib/wg-free-mesh", 0o755); err != nil {
		return err
	}
	if err := os.MkdirAll("/var/log/wg-free-mesh", 0o755); err != nil {
		return err
	}
	if err := os.MkdirAll("/etc/wg-free-mesh/profiles", 0o700); err != nil {
		return err
	}
	if err := installPath(); err != nil {
		return err
	}
	if err := os.WriteFile(systemdUnit, []byte(unit), 0o644); err != nil {
		return err
	}
	if err := run("systemctl", "daemon-reload"); err != nil {
		return err
	}
	if err := run("systemctl", "enable", "wfm-agent.service"); err != nil {
		return err
	}
	return Restart()
}

func Uninstall() error {
	if err := requireRoot(); err != nil {
		return err
	}
	_ = Stop()
	_ = run("systemctl", "disable", "wfm-agent.service")
	_ = uninstallPath()
	_ = os.Remove(systemdUnit)
	return run("systemctl", "daemon-reload")
}

func Start() error {
	if err := requireRoot(); err != nil {
		return err
	}
	return run("systemctl", "start", "wfm-agent.service")
}

func Stop() error {
	if err := requireRoot(); err != nil {
		return err
	}
	return run("systemctl", "stop", "wfm-agent.service")
}

func Restart() error {
	if err := requireRoot(); err != nil {
		return err
	}
	return run("systemctl", "restart", "wfm-agent.service")
}

func platformStatus() (StatusInfo, error) {
	installed := fileExists(systemdUnit)
	active := strings.TrimSpace(commandText("systemctl", "is-active", "wfm-agent.service"))
	enabled := strings.TrimSpace(commandText("systemctl", "is-enabled", "wfm-agent.service"))
	if !installed {
		return StatusInfo{Installed: false, State: "not-installed"}, nil
	}
	state := active
	if state == "" {
		state = "unknown"
	}
	return StatusInfo{
		Installed: true,
		Autostart: enabled == "enabled",
		Running:   active == "active",
		State:     state,
		Binary:    systemdExecStart(),
	}, nil
}

func platformLogs(lines int) error {
	return run("journalctl", "-u", "wfm-agent.service", "-n", fmt.Sprint(lines), "--no-pager")
}

func platformPurgeData() error {
	for _, path := range []string{
		"/etc/wg-free-mesh",
		"/var/lib/wg-free-mesh",
		"/var/log/wg-free-mesh",
	} {
		if err := os.RemoveAll(path); err != nil {
			return err
		}
	}
	return nil
}

func RunAgentService(runner Runner) error {
	return runner(context.Background(), os.Stderr)
}

func run(name string, args ...string) error {
	cmd := exec.Command(name, args...)
	output, err := cmd.CombinedOutput()
	text := strings.TrimRight(string(output), "\n")
	if err != nil {
		if text != "" {
			return fmt.Errorf("%s %s failed: %w\n%s", name, strings.Join(args, " "), err, text)
		}
		return fmt.Errorf("%s %s failed: %w", name, strings.Join(args, " "), err)
	}
	if text != "" {
		fmt.Println(text)
	}
	return nil
}

func commandText(name string, args ...string) string {
	output, _ := exec.Command(name, args...).CombinedOutput()
	return string(output)
}

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

func systemdExecStart() string {
	body, err := os.ReadFile(systemdUnit)
	if err != nil {
		return ""
	}
	for _, line := range strings.Split(string(body), "\n") {
		if strings.HasPrefix(line, "ExecStart=") {
			return strings.TrimSpace(strings.TrimPrefix(line, "ExecStart="))
		}
	}
	return ""
}

func agentPath() (string, error) {
	exe, err := os.Executable()
	if err != nil {
		return "", err
	}
	dir := filepath.Dir(exe)
	base := filepath.Base(exe)
	candidates := []string{filepath.Join(dir, "wfm-agent")}
	if strings.HasPrefix(base, "wfmctl") {
		candidates = append([]string{filepath.Join(dir, strings.Replace(base, "wfmctl", "wfm-agent", 1))}, candidates...)
	}
	for _, candidate := range candidates {
		if _, err := os.Stat(candidate); err == nil {
			return candidate, nil
		}
	}
	return "", fmt.Errorf("wfm-agent not found next to %s", exe)
}

func requireRoot() error {
	if os.Geteuid() != 0 {
		return fmt.Errorf("root privileges required; run with sudo")
	}
	return nil
}

func installPath() error {
	exe, err := os.Executable()
	if err != nil {
		return err
	}
	if err := os.MkdirAll("/usr/local/bin", 0o755); err != nil {
		return err
	}
	_ = os.Remove("/usr/local/bin/wfmctl")
	return os.Symlink(exe, "/usr/local/bin/wfmctl")
}

func uninstallPath() error {
	if err := os.Remove("/usr/local/bin/wfmctl"); err != nil && !os.IsNotExist(err) {
		return err
	}
	return nil
}
