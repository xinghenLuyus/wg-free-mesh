package service

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"syscall"
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
	agentPath, err := agentPath()
	if err != nil {
		return err
	}
	binPath := fmt.Sprintf(`"%s" %s`, agentPath, serviceArg)
	if err := run("install", "sc.exe", "create", Name, "binPath=", binPath, "DisplayName=", DisplayName, "start=", "auto"); err != nil {
		return err
	}
	fmt.Printf("Service %s installed.\n", Name)
	return nil
}

func Uninstall() error {
	if err := run("uninstall", "sc.exe", "delete", Name); err != nil {
		return err
	}
	fmt.Printf("Service %s uninstalled.\n", Name)
	return nil
}

func Start() error {
	if err := run("start", "sc.exe", "start", Name); err != nil {
		return err
	}
	fmt.Printf("Service %s start requested.\n", Name)
	return nil
}

func Stop() error {
	if err := run("stop", "sc.exe", "stop", Name); err != nil {
		return err
	}
	fmt.Printf("Service %s stop requested.\n", Name)
	return nil
}

func Status() error {
	output, err := commandOutput("status", "sc.exe", "query", Name)
	if err != nil {
		return err
	}
	fmt.Printf("Service %s status: %s\n", Name, parseServiceState(output))
	return nil
}

func Restart() error {
	_ = Stop()
	return Start()
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
	err := activeRunner(ctx, os.Stderr)
	if err != nil {
		fmt.Fprintf(os.Stderr, "agent failed: %v\n", err)
	}
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

func run(action string, name string, args ...string) error {
	cmd := exec.Command(name, args...)
	if err := cmd.Run(); err != nil {
		return friendlyCommandError(action, err)
	}
	return nil
}

func commandOutput(action string, name string, args ...string) (string, error) {
	cmd := exec.Command(name, args...)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return "", friendlyCommandError(action, err)
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

func friendlyCommandError(action string, err error) error {
	if exitErr, ok := err.(*exec.ExitError); ok {
		switch exitErr.ExitCode() {
		case 5:
			return fmt.Errorf("%s requires administrator privileges; run PowerShell as Administrator", action)
		case 1060:
			return fmt.Errorf("service %s is not installed; run `wfmctl service install` first", Name)
		case 1072:
			return fmt.Errorf("service %s is marked for deletion; close Services consoles and retry later", Name)
		case 1073:
			return fmt.Errorf("service %s is already installed", Name)
		case 1056:
			return fmt.Errorf("service %s is already running", Name)
		case 1062:
			return fmt.Errorf("service %s is not running", Name)
		default:
			return fmt.Errorf("%s failed with Windows service exit code %d", action, exitErr.ExitCode())
		}
	}
	return err
}
