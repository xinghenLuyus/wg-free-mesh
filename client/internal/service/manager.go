package service

import (
	"context"
	"fmt"
	"io"
	"strings"

	"wfm/client/internal/profile"
)

const (
	Name        = "WfmAgent"
	DisplayName = "WG Free Mesh Agent"
)

type Runner func(ctx context.Context, stderr io.Writer) error

type StatusInfo struct {
	Installed bool
	Autostart bool
	Running   bool
	State     string
	Binary    string
	Detail    string
}

func Status() error {
	info, err := platformStatus()
	if err != nil {
		return err
	}
	printStatus(info)
	return nil
}

func Logs(lines int) error {
	if lines <= 0 {
		lines = 100
	}
	return platformLogs(lines)
}

func IsRunning() (bool, error) {
	info, err := platformStatus()
	if err != nil {
		return false, err
	}
	return info.Running, nil
}

func PurgeData() error {
	return platformPurgeData()
}

func printStatus(info StatusInfo) {
	fmt.Printf("Service: %s\n", Name)
	fmt.Printf("State: %s\n", normalizedState(info))
	fmt.Printf("Installed: %s\n", yesNo(info.Installed))
	fmt.Printf("Autostart: %s\n", yesNo(info.Autostart))
	if info.Binary != "" {
		fmt.Printf("Binary: %s\n", info.Binary)
	}
	if info.Detail != "" {
		fmt.Printf("Detail: %s\n", info.Detail)
	}
	printProfileSummary()
}

func printProfileSummary() {
	summaries, root, err := profile.Summaries()
	if err != nil {
		fmt.Printf("Profiles: error (%v)\n", err)
		return
	}
	fmt.Printf("Profile root: %s\n", root)
	fmt.Printf("Profiles: %d\n", len(summaries))
	for _, item := range summaries {
		fmt.Printf("  %s | %s/%s | profile=%s desired=%s mqtt=%s:%d tls=%t\n",
			item.ProfileID,
			item.ConfigName,
			item.NodeName,
			presence(item.ProfilePresent, item.ProfileValid),
			presence(item.DesiredPresent, true),
			item.MQTTHost,
			item.MQTTPort,
			item.MQTTTLS,
		)
		if item.ServerURL != "" {
			fmt.Printf("    server=%s\n", item.ServerURL)
		}
	}
}

func normalizedState(info StatusInfo) string {
	if !info.Installed {
		return "not-installed"
	}
	if info.Running {
		return "running"
	}
	if info.State != "" {
		return info.State
	}
	return "stopped"
}

func yesNo(value bool) string {
	if value {
		return "yes"
	}
	return "no"
}

func presence(present bool, valid bool) string {
	if !present {
		return "missing"
	}
	if !valid {
		return "invalid"
	}
	return "present"
}

func printLastLines(text string, lines int) {
	if lines <= 0 {
		lines = 100
	}
	parts := strings.Split(strings.TrimRight(text, "\n"), "\n")
	start := 0
	if len(parts) > lines {
		start = len(parts) - lines
	}
	for _, line := range parts[start:] {
		fmt.Println(line)
	}
}
