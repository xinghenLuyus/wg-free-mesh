package service

import (
	"context"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

const serviceArg = "service-run"

var (
	advapi32                         = syscall.NewLazyDLL("advapi32.dll")
	procStartServiceCtrlDispatcherW  = advapi32.NewProc("StartServiceCtrlDispatcherW")
	procRegisterServiceCtrlHandlerEx = advapi32.NewProc("RegisterServiceCtrlHandlerExW")
	procSetServiceStatus             = advapi32.NewProc("SetServiceStatus")
)

const (
	serviceWin32OwnProcess = 0x00000010
	serviceStopped         = 0x00000001
	serviceStartPending    = 0x00000002
	serviceStopPending     = 0x00000003
	serviceRunning         = 0x00000004
	serviceAcceptStop      = 0x00000001
	serviceAcceptShutdown  = 0x00000004
	serviceControlStop     = 0x00000001
	serviceControlShutdown = 0x00000005
)

type serviceTableEntry struct {
	serviceName *uint16
	serviceProc uintptr
}

type serviceStatus struct {
	serviceType             uint32
	currentState            uint32
	controlsAccepted        uint32
	win32ExitCode           uint32
	serviceSpecificExitCode uint32
	checkPoint              uint32
	waitHint                uint32
}

var activeRunner Runner
var activeCancel context.CancelFunc
var activeStatusHandle uintptr

func Install() error {
	if err := requireAdministrator(); err != nil {
		return err
	}
	if err := ensureDirs(); err != nil {
		return err
	}
	if err := installPath(); err != nil {
		return err
	}
	agentPath, err := agentPath()
	if err != nil {
		return err
	}
	binPath := fmt.Sprintf(`"%s" %s`, agentPath, serviceArg)
	if err := run("install", "sc.exe", "create", Name, "binPath=", binPath, "DisplayName=", DisplayName, "start=", "auto", "obj=", "LocalSystem"); err != nil {
		if strings.Contains(err.Error(), "already installed") {
			fmt.Printf("Service %s already installed.\n", Name)
			if err := run("configure", "sc.exe", "config", Name, "binPath=", binPath, "DisplayName=", DisplayName, "start=", "auto", "obj=", "LocalSystem"); err != nil {
				return err
			}
			return Restart()
		}
		return err
	}
	fmt.Printf("Service %s installed.\n", Name)
	return Start()
}

func Uninstall() error {
	if err := requireAdministrator(); err != nil {
		return err
	}
	_ = Stop()
	_ = uninstallPath()
	if err := run("uninstall", "sc.exe", "delete", Name); err != nil {
		if strings.Contains(err.Error(), "not installed") {
			fmt.Printf("Service %s is not installed.\n", Name)
			return nil
		}
		return err
	}
	fmt.Printf("Service %s uninstalled.\n", Name)
	return nil
}

func Start() error {
	if err := requireAdministrator(); err != nil {
		return err
	}
	if err := startServiceRequest(); err != nil {
		return err
	}
	fmt.Printf("Service %s start requested.\n", Name)
	return nil
}

func Stop() error {
	if err := requireAdministrator(); err != nil {
		return err
	}
	if err := stopServiceRequest(); err != nil {
		return err
	}
	fmt.Printf("Service %s stop requested.\n", Name)
	return nil
}

func Restart() error {
	if err := requireAdministrator(); err != nil {
		return err
	}
	info, err := platformStatus()
	if err != nil {
		return err
	}
	if info.Installed && info.State != "stopped" {
		_ = stopServiceRequest()
		if err := waitForServiceState("stopped", 30*time.Second); err != nil {
			return err
		}
	}
	return Start()
}

func platformStatus() (StatusInfo, error) {
	output, err := exec.Command("sc.exe", "query", Name).CombinedOutput()
	if err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok && exitErr.ExitCode() == 1060 {
			return StatusInfo{Installed: false, State: "not-installed"}, nil
		}
		return StatusInfo{}, fmt.Errorf("status failed: %w\n%s", err, strings.TrimSpace(string(output)))
	}
	state := strings.ToLower(parseServiceState(string(output)))
	config, _ := exec.Command("sc.exe", "qc", Name).CombinedOutput()
	return StatusInfo{
		Installed: true,
		Autostart: strings.Contains(strings.ToUpper(string(config)), "AUTO_START"),
		Running:   state == "running",
		State:     state,
		Binary:    parseBinaryPath(string(config)),
	}, nil
}

func platformLogs(lines int) error {
	path := filepath.Join(logDir(), "wfm-agent.log")
	body, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			fmt.Printf("No log file found at %s\n", path)
			return nil
		}
		return err
	}
	if strings.TrimSpace(string(body)) == "" {
		fmt.Printf("Log file is empty: %s\n", path)
		return nil
	}
	printLastLines(string(body), lines)
	return nil
}

func platformPurgeData() error {
	root := filepath.Join(programData(), "wg-free-mesh")
	return os.RemoveAll(root)
}

func RunAgentService(runner Runner) error {
	activeRunner = runner
	name, err := syscall.UTF16PtrFromString(Name)
	if err != nil {
		return err
	}
	table := []serviceTableEntry{
		{serviceName: name, serviceProc: syscall.NewCallback(serviceMain)},
		{},
	}
	ret, _, callErr := procStartServiceCtrlDispatcherW.Call(uintptr(unsafe.Pointer(&table[0])))
	if ret == 0 {
		return callErr
	}
	return nil
}

func serviceMain(argc uint32, argv **uint16) uintptr {
	name, _ := syscall.UTF16PtrFromString(Name)
	handle, _, _ := procRegisterServiceCtrlHandlerEx.Call(
		uintptr(unsafe.Pointer(name)),
		syscall.NewCallback(serviceHandler),
		0,
	)
	activeStatusHandle = handle
	setStatus(serviceStartPending, 0)
	ctx, cancel := context.WithCancel(context.Background())
	activeCancel = cancel
	setStatus(serviceRunning, serviceAcceptStop|serviceAcceptShutdown)
	stderr := serviceLogWriter()
	fmt.Fprintf(stderr, "service started at %s\n", time.Now().Format(time.RFC3339))
	err := activeRunner(ctx, stderr)
	if err != nil {
		fmt.Fprintf(stderr, "agent failed: %v\n", err)
	}
	fmt.Fprintf(stderr, "service stopped at %s\n", time.Now().Format(time.RFC3339))
	setStatus(serviceStopped, 0)
	return 0
}

func serviceHandler(control uint32, eventType uint32, eventData uintptr, context uintptr) uintptr {
	if control == serviceControlStop || control == serviceControlShutdown {
		setStatus(serviceStopPending, 0)
		if activeCancel != nil {
			activeCancel()
		}
		return 0
	}
	return 0
}

func setStatus(state uint32, accepted uint32) {
	status := serviceStatus{
		serviceType:      serviceWin32OwnProcess,
		currentState:     state,
		controlsAccepted: accepted,
	}
	procSetServiceStatus.Call(activeStatusHandle, uintptr(unsafe.Pointer(&status)))
}

func agentPath() (string, error) {
	exe, err := os.Executable()
	if err != nil {
		return "", err
	}
	dir := filepath.Dir(exe)
	candidate := filepath.Join(dir, "wfm-agent.exe")
	if _, err := os.Stat(candidate); err == nil {
		return candidate, nil
	}
	return "", fmt.Errorf("wfm-agent.exe not found next to %s", exe)
}

func ensureDirs() error {
	for _, dir := range []string{
		filepath.Join(programData(), "wg-free-mesh", "profiles"),
		filepath.Join(programData(), "wg-free-mesh", "runtime"),
		logDir(),
	} {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return err
		}
	}
	return nil
}

func programData() string {
	base := os.Getenv("ProgramData")
	if base == "" {
		return `C:\ProgramData`
	}
	return base
}

func logDir() string {
	return filepath.Join(programData(), "wg-free-mesh", "logs")
}

func serviceLogWriter() io.Writer {
	if err := os.MkdirAll(logDir(), 0o755); err != nil {
		return os.Stderr
	}
	file, err := os.OpenFile(filepath.Join(logDir(), "wfm-agent.log"), os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
	if err != nil {
		return os.Stderr
	}
	return resilientMultiWriter(file, os.Stderr)
}

type resilientWriter struct {
	writers []io.Writer
}

func resilientMultiWriter(writers ...io.Writer) io.Writer {
	return resilientWriter{writers: writers}
}

func (w resilientWriter) Write(p []byte) (int, error) {
	wrote := false
	for _, writer := range w.writers {
		if writer == nil {
			continue
		}
		if _, err := writer.Write(p); err == nil {
			wrote = true
		}
	}
	if !wrote {
		return 0, fmt.Errorf("all log writers failed")
	}
	return len(p), nil
}

func requireAdministrator() error {
	cmd := exec.Command("net", "session")
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("administrator privileges required; run PowerShell as Administrator")
	}
	return nil
}

func installPath() error {
	dir := executableDir()
	quotedDir := psQuote(dir)
	script := fmt.Sprintf(`$dir = %s; $paths = [Environment]::GetEnvironmentVariable('Path', 'Machine') -split ';' | Where-Object { $_ -and $_ -ine $dir }; [Environment]::SetEnvironmentVariable('Path', (($paths + $dir) -join ';'), 'Machine')`, quotedDir)
	cmd := exec.Command("powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("install PATH failed: %w\n%s", err, strings.TrimSpace(string(output)))
	}
	return nil
}

func uninstallPath() error {
	dir := executableDir()
	quotedDir := psQuote(dir)
	script := fmt.Sprintf(`$dir = %s; $paths = [Environment]::GetEnvironmentVariable('Path', 'Machine') -split ';' | Where-Object { $_ -and $_ -ine $dir }; [Environment]::SetEnvironmentVariable('Path', ($paths -join ';'), 'Machine')`, quotedDir)
	cmd := exec.Command("powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("uninstall PATH failed: %w\n%s", err, strings.TrimSpace(string(output)))
	}
	return nil
}

func executableDir() string {
	exe, err := os.Executable()
	if err != nil {
		return "."
	}
	return filepath.Dir(exe)
}

func psQuote(value string) string {
	return "'" + strings.ReplaceAll(value, "'", "''") + "'"
}

func run(action string, name string, args ...string) error {
	cmd := exec.Command(name, args...)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return friendlyCommandError(action, err, strings.TrimSpace(string(output)))
	}
	return nil
}

func startServiceRequest() error {
	cmd := exec.Command("sc.exe", "start", Name)
	output, err := cmd.CombinedOutput()
	if err == nil {
		return nil
	}
	if exitErr, ok := err.(*exec.ExitError); ok && exitErr.ExitCode() == 1056 {
		return nil
	}
	return friendlyCommandError("start", err, strings.TrimSpace(string(output)))
}

func stopServiceRequest() error {
	cmd := exec.Command("sc.exe", "stop", Name)
	output, err := cmd.CombinedOutput()
	if err == nil {
		return nil
	}
	if exitErr, ok := err.(*exec.ExitError); ok && exitErr.ExitCode() == 1062 {
		return nil
	}
	return friendlyCommandError("stop", err, strings.TrimSpace(string(output)))
}

func waitForServiceState(target string, timeout time.Duration) error {
	deadline := time.Now().Add(timeout)
	var lastState string
	for {
		info, err := platformStatus()
		if err != nil {
			return err
		}
		lastState = info.State
		if lastState == target {
			return nil
		}
		if time.Now().After(deadline) {
			return fmt.Errorf("service %s did not reach %s state within %s; last state: %s", Name, target, timeout, lastState)
		}
		time.Sleep(500 * time.Millisecond)
	}
}

func commandOutput(action string, name string, args ...string) (string, error) {
	cmd := exec.Command(name, args...)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return "", friendlyCommandError(action, err, strings.TrimSpace(string(output)))
	}
	return string(output), nil
}

func parseServiceState(output string) string {
	matches := regexp.MustCompile(`STATE\s+:\s+\d+\s+([A-Z_]+)`).FindStringSubmatch(output)
	if len(matches) == 2 {
		return matches[1]
	}
	return "UNKNOWN"
}

func parseBinaryPath(output string) string {
	matches := regexp.MustCompile(`BINARY_PATH_NAME\s+:\s+(.+)`).FindStringSubmatch(output)
	if len(matches) == 2 {
		return strings.TrimSpace(matches[1])
	}
	return ""
}

func friendlyCommandError(action string, err error, detail string) error {
	withDetail := func(base error) error {
		if detail == "" {
			return base
		}
		return fmt.Errorf("%v\n%s", base, detail)
	}
	if exitErr, ok := err.(*exec.ExitError); ok {
		switch exitErr.ExitCode() {
		case 5:
			return withDetail(fmt.Errorf("%s requires administrator privileges; run PowerShell as Administrator", action))
		case 1060:
			return withDetail(fmt.Errorf("service %s is not installed; run `wfmctl install` first", Name))
		case 1072:
			return withDetail(fmt.Errorf("service %s is marked for deletion; close Services consoles and retry later", Name))
		case 1073:
			return withDetail(fmt.Errorf("service %s is already installed", Name))
		case 1056:
			return withDetail(fmt.Errorf("service %s is already running", Name))
		case 1062:
			return withDetail(fmt.Errorf("service %s is not running", Name))
		default:
			return withDetail(fmt.Errorf("%s failed with Windows service exit code %d", action, exitErr.ExitCode()))
		}
	}
	return withDetail(err)
}
