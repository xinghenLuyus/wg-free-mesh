package service

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

const plistPath = "/Library/LaunchDaemons/mesh.wg-free.wfm-agent.plist"

func Install() error {
	if err := requireRoot(); err != nil {
		return err
	}
	agentPath, err := agentPath()
	if err != nil {
		return err
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
	if err := installPath(); err != nil {
		return err
	}
	if err := os.WriteFile(plistPath, []byte(plist), 0o644); err != nil {
		return err
	}
	_ = run("launchctl", "bootout", "system/mesh.wg-free.wfm-agent")
	if err := Start(); err != nil {
		return err
	}
	printInstallDiagnostics()
	return nil
}

func Uninstall() error {
	if err := requireRoot(); err != nil {
		return err
	}
	_ = run("launchctl", "bootout", "system/mesh.wg-free.wfm-agent")
	_ = uninstallPath()
	if err := os.Remove(plistPath); err != nil && !os.IsNotExist(err) {
		return err
	}
	return nil
}

func Start() error {
	if err := requireRoot(); err != nil {
		return err
	}
	if err := run("launchctl", "bootstrap", "system", plistPath); err == nil {
		return nil
	}
	return run("launchctl", "kickstart", "-k", "system/mesh.wg-free.wfm-agent")
}

func Stop() error {
	if err := requireRoot(); err != nil {
		return err
	}
	return run("launchctl", "bootout", "system/mesh.wg-free.wfm-agent")
}

func Restart() error {
	if err := requireRoot(); err != nil {
		return err
	}
	_ = Stop()
	return Start()
}

func platformStatus() (StatusInfo, error) {
	installed := fileExists(plistPath)
	output := commandText("launchctl", "print", "system/mesh.wg-free.wfm-agent")
	running := strings.Contains(output, "state = running")
	state := "stopped"
	if running {
		state = "running"
	} else if output == "" {
		state = "not-loaded"
	}
	return StatusInfo{
		Installed: installed,
		Autostart: installed,
		Running:   running,
		State:     state,
		Binary:    plistProgramPath(),
	}, nil
}

func platformLogs(lines int) error {
	for _, path := range []string{
		"/Library/Logs/wg-free-mesh/wfm-agent.log",
		"/Library/Logs/wg-free-mesh/wfm-agent.err.log",
	} {
		body, err := os.ReadFile(path)
		if err == nil {
			fmt.Printf("==> %s <==\n", path)
			printLastLines(string(body), lines)
		}
	}
	return nil
}

func platformPurgeData() error {
	for _, path := range []string{
		"/Library/Application Support/WG Free Mesh",
		"/Library/Logs/wg-free-mesh",
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

func plistProgramPath() string {
	body, err := os.ReadFile(plistPath)
	if err != nil {
		return ""
	}
	text := string(body)
	key := "<key>ProgramArguments</key>"
	index := strings.Index(text, key)
	if index < 0 {
		return ""
	}
	rest := text[index+len(key):]
	startTag := "<string>"
	endTag := "</string>"
	start := strings.Index(rest, startTag)
	if start < 0 {
		return ""
	}
	start += len(startTag)
	end := strings.Index(rest[start:], endTag)
	if end < 0 {
		return ""
	}
	return strings.TrimSpace(rest[start : start+end])
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
