package mqtt

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"wfm/client/internal/profile"
)

func TestQueryDistinguishesAbsentFromFailure(t *testing.T) {
	original := readTool
	t.Cleanup(func() { readTool = original })
	readTool = func(string, ...string) (string, error) { return "", nil }
	if device, _, err := queryDevice("utun4", "wireguard"); err != nil || device != "" {
		t.Fatal("absence must be explicit", device, err)
	}
	readTool = func(string, ...string) (string, error) { return "", errors.New("permission denied") }
	if _, _, err := queryDevice("utun4", "wireguard"); err == nil {
		t.Fatal("query failure treated as absence")
	}
	readTool = func(_ string, args ...string) (string, error) {
		if args[len(args)-1] == "interfaces" {
			return "utun4", nil
		}
		return "public-key", nil
	}
	if device, key, err := queryDevice("utun4", "wireguard"); err != nil || device != "utun4" || key != "public-key" {
		t.Fatal(device, key, err)
	}
}

func TestGenerationMoveCanResumeWithoutOverwriting(t *testing.T) {
	dir := t.TempDir()
	if err := os.Mkdir(filepath.Join(dir, "config"), 0o700); err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 2; i++ {
		if err := moveGeneration(dir, "config", "config.old"); err != nil {
			t.Fatal(err)
		}
	}
	if err := os.Mkdir(filepath.Join(dir, "config"), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := moveGeneration(dir, "config", "config.old"); err == nil {
		t.Fatal("overwrote history")
	}
}

func TestTransitionPersistsIntentWithoutCredentials(t *testing.T) {
	dir := t.TempDir()
	target := transition{Phase: "prepared", WasRunning: true, Next: profile.ProfileMeta{ProfileID: "p", ConfigID: "cfg", NodeID: "node", InterfaceName: "new"}}
	if err := profile.AtomicJSON(filepath.Join(dir, "transition.json"), target); err != nil {
		t.Fatal(err)
	}
	restored, err := readTransition(dir)
	if err != nil || restored == nil || !restored.WasRunning || restored.Next.InterfaceName != "new" {
		t.Fatal(restored, err)
	}
	body, err := os.ReadFile(filepath.Join(dir, "transition.json"))
	if err != nil || strings.Contains(string(body), "password") {
		t.Fatal("unexpected credential data")
	}
	if err = removeTransition(dir); err != nil {
		t.Fatal(err)
	}
	if restored, err = readTransition(dir); err != nil || restored != nil {
		t.Fatal(restored, err)
	}
}
