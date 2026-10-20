package profile

import (
	"os"
	"path/filepath"
	"testing"
)

func TestWritableDirectoryProbeLeavesNoFiles(t *testing.T) {
	root := filepath.Join(t.TempDir(), "profiles")
	if err := checkWritableDirectory(root); err != nil {
		t.Fatal(err)
	}
	entries, err := os.ReadDir(root)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 0 {
		t.Fatalf("write probe left files behind: %v", entries)
	}
}

func TestWritableDirectoryProbeRejectsFilePath(t *testing.T) {
	root := filepath.Join(t.TempDir(), "profiles")
	if err := os.WriteFile(root, []byte("existing data"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := checkWritableDirectory(root); err == nil {
		t.Fatal("a file cannot be used as a profile directory")
	}
	data, err := os.ReadFile(root)
	if err != nil || string(data) != "existing data" {
		t.Fatalf("existing file was changed: %q, %v", data, err)
	}
}
