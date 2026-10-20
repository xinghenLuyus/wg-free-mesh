package service

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

const plistPath = "/Library/LaunchDaemons/mesh.wg-free.wfm-agent.plist"
const launchdTarget = "system/mesh.wg-free.wfm-agent"

var launchctlCommand = func(args ...string) (string, error) {
	output, err := exec.Command("launchctl", args...).CombinedOutput()
	return strings.TrimSpace(string(output)), err
}

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
    <key>EnvironmentVariables</key>
    <dict>
      <key>PATH</key>
      <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
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
	enableIPv4Forwarding()
	if err := os.WriteFile(plistPath, []byte(plist), 0o644); err != nil {
		return err
	}
	if err := Stop(); err != nil {
		return err
	}
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
	if err := Stop(); err != nil {
		return err
	}
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
	return startLaunchd(false)
}

func Stop() error {
	if err := requireRoot(); err != nil {
		return err
	}
	return stopLaunchd()
}

func Restart() error {
	if err := requireRoot(); err != nil {
		return err
	}
	return startLaunchd(true)
}

func platformStatus() (StatusInfo, error) {
	installed := fileExists(plistPath)
	output, loaded, err := launchdStatus()
	if err != nil {
		return StatusInfo{}, err
	}
	running := strings.Contains(output, "state = running")
	state := "stopped"
	if running {
		state = "running"
	} else if !loaded {
		state = "not-loaded"
	}
	return StatusInfo{
		Installed: installed || loaded,
		Autostart: installed,
		Running:   running,
		State:     state,
		Binary:    plistProgramPath(),
	}, nil
}

func startLaunchd(restart bool) error {
	_, loaded, err := launchdStatus()
	if err != nil {
		return err
	}
	if !loaded {
		return runLaunchctl("bootstrap", "system", plistPath)
	}
	if restart {
		return runLaunchctl("kickstart", "-k", launchdTarget)
	}
	return runLaunchctl("kickstart", launchdTarget)
}

func stopLaunchd() error {
	_, loaded, err := launchdStatus()
	if err != nil || !loaded {
		return err
	}
	if err := runLaunchctl("bootout", launchdTarget); err != nil {
		return err
	}
	deadline := time.Now().Add(10 * time.Second)
	for {
		_, loaded, err = launchdStatus()
		if err != nil || !loaded {
			return err
		}
		if time.Now().After(deadline) {
			return fmt.Errorf("service %s was not unloaded within 10 seconds; retry after checking launchctl status", launchdTarget)
		}
		time.Sleep(100 * time.Millisecond)
	}
}

func launchdStatus() (string, bool, error) {
	output, err := launchctlCommand("print", launchdTarget)
	if err == nil {
		return output, true, nil
	}
	var exitErr *exec.ExitError
	if errors.As(err, &exitErr) && exitErr.ExitCode() == 113 || strings.Contains(output, "Could not find service") {
		return "", false, nil
	}
	return "", false, fmt.Errorf("launchctl print %s failed: %w\n%s", launchdTarget, err, output)
}

func runLaunchctl(args ...string) error {
	output, err := launchctlCommand(args...)
	if err != nil {
		return fmt.Errorf("launchctl %s failed: %w\n%s", strings.Join(args, " "), err, output)
	}
	if output != "" {
		fmt.Println(output)
	}
	return nil
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

func requireBindPrivileges() error {
	return requireRoot()
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

func enableIPv4Forwarding() {
	if err := run("sysctl", "-w", "net.inet.ip.forwarding=1"); err != nil {
		fmt.Printf("[error] IPv4 forwarding setup failed: %s\n", firstLine(err.Error()))
	}
}
