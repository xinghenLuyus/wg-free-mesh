package service

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"strings"
)

const plistPath = "/Library/LaunchDaemons/mesh.wg-free.wfm-agent.plist"

func Install() error {
	agentPath, err := os.Executable()
	if err != nil {
		return err
	}
	if strings.HasSuffix(agentPath, "wfmctl") {
		agentPath = strings.TrimSuffix(agentPath, "wfmctl") + "wfm-agent"
	}
	plist := fmt.Sprintf(`<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>mesh.wg-free.wfm-agent</string>
    <key>ProgramArguments</key>
    <array>
      <string>%s</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>/Library/Application Support/WG Free Mesh</string>
    <key>StandardOutPath</key>
    <string>/Library/Logs/wg-free-mesh/wfm-agent.log</string>
    <key>StandardErrorPath</key>
    <string>/Library/Logs/wg-free-mesh/wfm-agent.err.log</string>
  </dict>
</plist>
`, agentPath)
	for _, dir := range []string{
		"/Library/Application Support/WG Free Mesh/profiles",
		"/Library/Application Support/WG Free Mesh/runtime",
		"/Library/Logs/wg-free-mesh",
	} {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return err
		}
	}
	if err := os.WriteFile(plistPath, []byte(plist), 0o644); err != nil {
		return err
	}
	_ = run("launchctl", "bootout", "system/mesh.wg-free.wfm-agent")
	return run("launchctl", "bootstrap", "system", plistPath)
}

func Uninstall() error {
	_ = run("launchctl", "bootout", "system/mesh.wg-free.wfm-agent")
	return os.Remove(plistPath)
}

func Start() error   { return run("launchctl", "kickstart", "-k", "system/mesh.wg-free.wfm-agent") }
func Stop() error    { return run("launchctl", "bootout", "system/mesh.wg-free.wfm-agent") }
func Status() error  { return run("launchctl", "print", "system/mesh.wg-free.wfm-agent") }
func Restart() error { return Start() }

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
