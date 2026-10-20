package service

import (
	"encoding/xml"
	"fmt"
	"os"
	"strconv"
	"strings"
)

func requestUpdateStop() error { return Stop() }

func updateStatus() (UpdateState, error) {
	body, err := os.ReadFile(plistPath)
	if err != nil {
		return UpdateState{}, fmt.Errorf("cannot read installed agent plist: %w", err)
	}
	decoder := xml.NewDecoder(strings.NewReader(string(body)))
	wantArray := false
	program := ""
	for {
		token, err := decoder.Token()
		if err != nil {
			break
		}
		start, ok := token.(xml.StartElement)
		if !ok {
			continue
		}
		if start.Name.Local == "key" {
			var key string
			if err = decoder.DecodeElement(&key, &start); err != nil {
				return UpdateState{}, err
			}
			wantArray = key == "ProgramArguments"
		}
		if wantArray && start.Name.Local == "string" {
			if err = decoder.DecodeElement(&program, &start); err != nil {
				return UpdateState{}, err
			}
			break
		}
	}
	if program == "" {
		return UpdateState{}, fmt.Errorf("cannot identify plist executable")
	}
	output, loaded, err := launchdStatus()
	if err != nil {
		return UpdateState{}, err
	}
	state := UpdateState{Binary: program, State: "stopped"}
	if !loaded {
		return state, nil
	}
	state.State = "pending"
	for _, line := range strings.Split(output, "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "program = ") {
			state.Binary = strings.TrimPrefix(line, "program = ")
		}
		if strings.HasPrefix(line, "pid = ") {
			state.PID, err = strconv.Atoi(strings.TrimPrefix(line, "pid = "))
			if err != nil {
				return state, err
			}
		}
		if line == "state = running" {
			state.Running = true
			state.State = "running"
		}
	}
	return state, nil
}
