package update

import (
	"syscall"
	"unsafe"
)

// ReplaceFile preserves the destination's ACL rather than inheriting a staging ACL.
func replacePlatform(from, to string) error {
	replacement, err := syscall.UTF16PtrFromString(from)
	if err != nil {
		return err
	}
	target, err := syscall.UTF16PtrFromString(to)
	if err != nil {
		return err
	}
	ok, _, err := syscall.NewLazyDLL("kernel32.dll").NewProc("ReplaceFileW").Call(uintptr(unsafe.Pointer(target)), uintptr(unsafe.Pointer(replacement)), 0, 0, 0, 0)
	if ok == 0 {
		return err
	}
	return nil
}
