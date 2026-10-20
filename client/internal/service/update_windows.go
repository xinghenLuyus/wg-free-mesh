package service

import (
	"context"
	"fmt"
	"os/exec"
	"runtime"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

var updateKernel = syscall.NewLazyDLL("kernel32.dll")

func requestUpdateStop() error {
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	body, err := exec.CommandContext(ctx, "sc.exe", "stop", Name).CombinedOutput()
	if err == nil {
		return nil
	}
	if exit, ok := err.(*exec.ExitError); ok && exit.ExitCode() == 1062 {
		return nil
	}
	return fmt.Errorf("stop agent for update: %w: %s", err, body)
}

func updateStatus() (UpdateState, error) {
	openManager := advapi32.NewProc("OpenSCManagerW")
	openService := advapi32.NewProc("OpenServiceW")
	closeHandle := advapi32.NewProc("CloseServiceHandle")
	manager, _, err := openManager.Call(0, 0, 1)
	if manager == 0 {
		return UpdateState{}, err
	}
	defer closeHandle.Call(manager)
	name, _ := syscall.UTF16PtrFromString(Name)
	handle, _, err := openService.Call(manager, uintptr(unsafe.Pointer(name)), 5)
	if handle == 0 {
		return UpdateState{}, fmt.Errorf("cannot open installed agent service: %w", err)
	}
	defer closeHandle.Call(handle)
	var status struct{ Type, State, Accepted, Exit, Specific, Checkpoint, WaitHint, PID, Flags uint32 }
	var needed uint32
	ok, _, err := advapi32.NewProc("QueryServiceStatusEx").Call(handle, 0, uintptr(unsafe.Pointer(&status)), unsafe.Sizeof(status), uintptr(unsafe.Pointer(&needed)))
	if ok == 0 {
		return UpdateState{}, err
	}
	advapi32.NewProc("QueryServiceConfigW").Call(handle, 0, 0, uintptr(unsafe.Pointer(&needed)))
	if needed == 0 || needed > 1024*1024 {
		return UpdateState{}, fmt.Errorf("invalid service configuration size")
	}
	buffer := make([]byte, needed)
	ok, _, err = advapi32.NewProc("QueryServiceConfigW").Call(handle, uintptr(unsafe.Pointer(&buffer[0])), uintptr(len(buffer)), uintptr(unsafe.Pointer(&needed)))
	if ok == 0 {
		return UpdateState{}, err
	}
	config := (*struct {
		Type, Start, Error uint32
		Binary             *uint16
	})(unsafe.Pointer(&buffer[0]))
	base, end := uintptr(unsafe.Pointer(&buffer[0])), uintptr(unsafe.Pointer(&buffer[0]))+uintptr(len(buffer))
	pointer := uintptr(unsafe.Pointer(config.Binary))
	if pointer < base || pointer >= end {
		return UpdateState{}, fmt.Errorf("invalid service binary path")
	}
	var units []uint16
	for offset := uintptr(0); pointer+offset+2 <= end; offset += 2 {
		v := *(*uint16)(unsafe.Add(unsafe.Pointer(config.Binary), offset))
		if v == 0 {
			break
		}
		units = append(units, v)
	}
	runtime.KeepAlive(buffer)
	command := strings.TrimSpace(syscall.UTF16ToString(units))
	var path string
	if strings.HasPrefix(command, `"`) {
		parts := strings.SplitN(command[1:], `"`, 2)
		if len(parts) != 2 {
			return UpdateState{}, fmt.Errorf("invalid quoted service path")
		}
		path = parts[0]
	} else {
		index := strings.Index(strings.ToLower(command), ".exe")
		if index < 0 {
			return UpdateState{}, fmt.Errorf("invalid service path")
		}
		path = command[:index+4]
	}
	state := "pending"
	if status.State == 1 {
		state = "stopped"
		status.PID = 0
	}
	if status.State == 4 {
		state = "running"
	}
	return UpdateState{Binary: path, Running: status.State == 4, PID: int(status.PID), State: state}, nil
}

func updateProcessAlive(pid int) (bool, error) {
	handle, _, err := updateKernel.NewProc("OpenProcess").Call(0x100000, 0, uintptr(pid))
	if handle == 0 {
		if err == syscall.Errno(87) {
			return false, nil
		}
		return false, err
	}
	defer updateKernel.NewProc("CloseHandle").Call(handle)
	result, _, err := updateKernel.NewProc("WaitForSingleObject").Call(handle, 0)
	if result == 0 {
		return false, nil
	}
	if result == 258 {
		return true, nil
	}
	return false, err
}

func secureUpdateRoot(path string) error {
	// Replace the DACL, not merely inherited entries: no explicit user grant may remain.
	sddl, _ := syscall.UTF16PtrFromString("O:BAG:SYD:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)")
	var descriptor uintptr
	ok, _, err := advapi32.NewProc("ConvertStringSecurityDescriptorToSecurityDescriptorW").Call(uintptr(unsafe.Pointer(sddl)), 1, uintptr(unsafe.Pointer(&descriptor)), 0)
	if ok == 0 {
		return fmt.Errorf("create update directory security descriptor: %w", err)
	}
	defer updateKernel.NewProc("LocalFree").Call(descriptor)
	name, err := syscall.UTF16PtrFromString(path)
	if err != nil {
		return err
	}
	ok, _, err = advapi32.NewProc("SetFileSecurityW").Call(uintptr(unsafe.Pointer(name)), 0x80000005, descriptor)
	if ok == 0 {
		return fmt.Errorf("secure update directory: %w", err)
	}
	return nil
}

func DetachUpdate(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{CreationFlags: 0x00000008 | 0x00000200}
}
