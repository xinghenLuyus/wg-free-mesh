package profile

import (
	"fmt"
	"os"
)

func CheckWritable() error {
	root, err := RootDir()
	if err != nil {
		return err
	}
	return checkWritableDirectory(root)
}

func checkWritableDirectory(root string) error {
	if err := os.MkdirAll(root, 0o700); err != nil {
		return fmt.Errorf("cannot create profile directory %q: %w", root, err)
	}
	probe, err := os.CreateTemp(root, ".bind-check-*")
	if err != nil {
		return fmt.Errorf("profile directory %q is not writable: %w", root, err)
	}
	defer os.Remove(probe.Name())
	_, writeErr := probe.WriteString("wfm")
	closeErr := probe.Close()
	if writeErr != nil {
		return fmt.Errorf("cannot write to profile directory %q: %w", root, writeErr)
	}
	if closeErr != nil {
		return fmt.Errorf("cannot close profile directory write probe %q: %w", root, closeErr)
	}
	if err := os.Remove(probe.Name()); err != nil {
		return fmt.Errorf("cannot remove profile directory write probe %q: %w", root, err)
	}
	return nil
}
