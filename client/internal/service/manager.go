package service

import (
	"context"
	_ "embed"
	"fmt"
	"io"
	"os/exec"
	"strings"
	"time"

	"wfm/client/internal/bind"
	"wfm/client/internal/profile"
)

//go:embed install_logo.txt
var installLogo string

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

func ReloadOrStart() error {
	info, err := platformStatus()
	if err != nil {
		return err
	}
	if !info.Installed {
		return nil
	}
	if info.Running {
		fmt.Println("Restarting service to apply changes.")
		return Restart()
	}
	fmt.Println("Starting service to apply changes.")
	return Start()
}

func PurgeData() error {
	return platformPurgeData()
}

func printInstallDiagnostics() {
	fmt.Print(installLogo)
	fmt.Printf("\n WG Free Mesh Client %s\n", bind.Version)
	fmt.Println("Kernel/toolchain check:")
	printToolchainCheck("wg", "WireGuard")
	printToolchainCheck("awg", "AmneziaWG")
	fmt.Println()
}

func printToolchainCheck(command string, label string) {
	path, err := exec.LookPath(command)
	if err != nil {
		fmt.Printf("  [missing] %-10s command %q not found. Download and install the matching kernel/toolchain from the WFM server download page when needed.\n", label, command)
		return
	}
	version, err := commandVersion(command)
	if err != nil {
		fmt.Printf("  [warn]    %-10s found at %s, but %q failed: %v\n", label, path, command+" -v", err)
		if version != "" {
			fmt.Printf("            output: %s\n", firstLine(version))
		}
		return
	}
	fmt.Printf("  [ok]      %-10s %s\n", label, firstLine(version))
}

func commandVersion(command string) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	output, err := exec.CommandContext(ctx, command, "-v").CombinedOutput()
	text := strings.TrimSpace(string(output))
	if ctx.Err() != nil {
		return text, ctx.Err()
	}
	return text, err
}

func firstLine(text string) string {
	for _, line := range strings.Split(strings.TrimSpace(text), "\n") {
		line = strings.TrimSpace(line)
		if line != "" {
			return line
		}
	}
	return "(no version output)"
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
