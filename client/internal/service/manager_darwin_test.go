package service

import (
	"errors"
	"reflect"
	"strings"
	"testing"
)

func TestLaunchdStartAndRestart(t *testing.T) {
	for _, tt := range []struct {
		name, failure   string
		loaded, restart bool
		want            []string
	}{
		{"start loaded", "", true, false, []string{"print " + launchdTarget, "kickstart " + launchdTarget}},
		{"restart loaded", "", true, true, []string{"print " + launchdTarget, "kickstart -k " + launchdTarget}},
		{"start unloaded", "", false, false, []string{"print " + launchdTarget, "bootstrap system " + plistPath}},
		{"restart unloaded", "", false, true, []string{"print " + launchdTarget, "bootstrap system " + plistPath}},
		{"bootstrap error", "bootstrap", false, true, []string{"print " + launchdTarget, "bootstrap system " + plistPath}},
		{"status error", "print", false, false, []string{"print " + launchdTarget}},
		{"restart error", "kickstart", true, true, []string{"print " + launchdTarget, "kickstart -k " + launchdTarget}},
	} {
		t.Run(tt.name, func(t *testing.T) {
			original := launchctlCommand
			t.Cleanup(func() { launchctlCommand = original })
			failure := errors.New("system command failed")
			var calls []string
			launchctlCommand = func(args ...string) (string, error) {
				calls = append(calls, strings.Join(args, " "))
				if args[0] == tt.failure {
					return "original launchctl diagnostic", failure
				}
				if args[0] == "print" {
					if tt.loaded {
						return "state = running", nil
					}
					return "Could not find service", errors.New("service missing")
				}
				return "", nil
			}
			err := startLaunchd(tt.restart)
			if tt.failure == "" && err != nil {
				t.Fatal(err)
			}
			if tt.failure != "" && (!errors.Is(err, failure) || !strings.Contains(err.Error(), "original launchctl diagnostic")) {
				t.Fatalf("original failure must be preserved, got %v", err)
			}
			if !reflect.DeepEqual(calls, tt.want) {
				t.Fatalf("got calls %v, want %v", calls, tt.want)
			}
		})
	}
}

func TestLaunchdStopWaitsBeforeRegisteringAgain(t *testing.T) {
	original := launchctlCommand
	t.Cleanup(func() { launchctlCommand = original })
	var calls []string
	prints := 0
	launchctlCommand = func(args ...string) (string, error) {
		calls = append(calls, strings.Join(args, " "))
		if args[0] == "print" {
			prints++
			if prints <= 2 {
				return "state = running", nil
			}
			return "Could not find service", errors.New("service missing")
		}
		return "", nil
	}
	if err := stopLaunchd(); err != nil {
		t.Fatal(err)
	}
	if err := startLaunchd(false); err != nil {
		t.Fatal(err)
	}
	want := []string{
		"print " + launchdTarget,
		"bootout " + launchdTarget,
		"print " + launchdTarget,
		"print " + launchdTarget,
		"print " + launchdTarget,
		"bootstrap system " + plistPath,
	}
	if !reflect.DeepEqual(calls, want) {
		t.Fatalf("registration must wait for unloading: got %v, want %v", calls, want)
	}
}

func TestLaunchdStopFailureIsPreserved(t *testing.T) {
	original := launchctlCommand
	t.Cleanup(func() { launchctlCommand = original })
	failure := errors.New("bootout rejected")
	launchctlCommand = func(args ...string) (string, error) {
		if args[0] == "print" {
			return "state = running", nil
		}
		return "original bootout diagnostic", failure
	}
	if err := stopLaunchd(); !errors.Is(err, failure) || !strings.Contains(err.Error(), "original bootout diagnostic") {
		t.Fatalf("stop must preserve the original failure, got %v", err)
	}
}
