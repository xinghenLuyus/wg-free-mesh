package service

import (
	"context"
	"fmt"
	"os/exec"
	"strconv"
	"strings"
	"time"
)

func requestUpdateStop() error {
	ctx, cancel := context.WithTimeout(context.Background(), 40*time.Second)
	defer cancel()
	body, err := exec.CommandContext(ctx, "systemctl", "stop", "wfm-agent.service").CombinedOutput()
	if err != nil {
		return fmt.Errorf("stop agent for update: %w: %s", err, body)
	}
	return nil
}

func updateStatus() (UpdateState, error) {
	body, err := exec.Command("systemctl", "show", "wfm-agent.service", "--property=LoadState,ActiveState,MainPID,ExecStart").CombinedOutput()
	if err != nil {
		return UpdateState{}, fmt.Errorf("cannot inspect systemd service: %w: %s", err, body)
	}
	values := map[string]string{}
	for _, line := range strings.Split(string(body), "\n") {
		parts := strings.SplitN(line, "=", 2)
		if len(parts) == 2 {
			values[parts[0]] = parts[1]
		}
	}
	if values["LoadState"] != "loaded" {
		return UpdateState{}, fmt.Errorf("agent service is not loaded; install or repair it first")
	}
	active := values["ActiveState"]
	pid, err := strconv.Atoi(values["MainPID"])
	if err != nil {
		return UpdateState{}, fmt.Errorf("invalid systemd process ID")
	}
	command := values["ExecStart"]
	start := strings.Index(command, "path=")
	if start < 0 {
		return UpdateState{}, fmt.Errorf("cannot identify service executable")
	}
	command = command[start+5:]
	end := strings.Index(command, " ;")
	if end < 0 {
		return UpdateState{}, fmt.Errorf("cannot parse service executable")
	}
	state := "pending"
	if active == "active" {
		state = "running"
	}
	if active == "inactive" || active == "failed" {
		state = "stopped"
	}
	return UpdateState{Binary: command[:end], Running: active == "active", PID: pid, State: state}, nil
}
