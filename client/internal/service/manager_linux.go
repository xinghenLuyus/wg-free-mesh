package service

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"strings"
)

const systemdUnit = `/etc/systemd/system/wfm-agent.service`

func Install() error {
	agentPath, err := os.Executable()
	if err != nil {
		return err
	}
	if strings.HasSuffix(agentPath, "wfmctl") {
		agentPath = strings.TrimSuffix(agentPath, "wfmctl") + "wfm-agent"
	}
	unit := fmt.Sprintf(`[Unit]
Description=WG Free Mesh Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=%s
Restart=always
RestartSec=5
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
	if err := os.WriteFile(systemdUnit, []byte(unit), 0o644); err != nil {
		return err
	}
	if err := run("systemctl", "daemon-reload"); err != nil {
		return err
	}
	return run("systemctl", "enable", "wfm-agent.service")
}

func Uninstall() error {
	_ = Stop()
	_ = run("systemctl", "disable", "wfm-agent.service")
	_ = os.Remove(systemdUnit)
	return run("systemctl", "daemon-reload")
}

func Start() error   { return run("systemctl", "start", "wfm-agent.service") }
func Stop() error    { return run("systemctl", "stop", "wfm-agent.service") }
func Status() error  { return run("systemctl", "status", "wfm-agent.service", "--no-pager") }
func Restart() error { return run("systemctl", "restart", "wfm-agent.service") }

func RunAgentService(runner Runner) error {
	return runner(context.Background(), os.Stderr)
}

func run(name string, args ...string) error {
	cmd := exec.Command(name, args...)
	output, err := cmd.CombinedOutput()
	if len(output) > 0 {
		fmt.Print(strings.TrimRight(string(output), "\n"))
		fmt.Println()
	}
	return err
}
