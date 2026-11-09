package mqtt

import (
	"context"
	"fmt"
	"os/exec"
	"strconv"
	"strings"
	"time"
)

func currentInterfaceOnly(payload map[string]any) (bool, bool) {
	v, exists := payload["current_interface_only"]
	if !exists {
		return false, true
	}
	b, ok := v.(bool)
	return b, ok
}

var showAllInterfaces = runWGShow

func (s *Session) showInformation(protocol string, only bool) (string, error) {
	if !only {
		return showAllInterfaces(protocol)
	}
	bundles, err := ownedRunning(s.profile)
	if err != nil {
		return "", err
	}
	if len(bundles) != 1 {
		return "", fmt.Errorf("expected exactly one owned running interface")
	}
	b := bundles[0]
	return runWGShowInterface(b.Manifest.InterfaceName, b.Manifest.Protocol)
}

// parsePeerSnapshot consumes only script-friendly, non-secret show fields.
func parsePeerSnapshot(handshakes, transfers string) ([]map[string]string, error) {
	peers := map[string]map[string]string{}
	for _, line := range strings.Split(strings.TrimSpace(handshakes), "\n") {
		if strings.TrimSpace(line) == "" {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) != 2 {
			return nil, fmt.Errorf("invalid handshake row")
		}
		if _, err := strconv.ParseUint(fields[1], 10, 64); err != nil {
			return nil, err
		}
		if peers[fields[0]] != nil {
			return nil, fmt.Errorf("duplicate peer")
		}
		peers[fields[0]] = map[string]string{"public_key": fields[0], "latest_handshake": fields[1]}
	}
	result := []map[string]string{}
	for _, line := range strings.Split(strings.TrimSpace(transfers), "\n") {
		if strings.TrimSpace(line) == "" {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) != 3 || peers[fields[0]] == nil {
			return nil, fmt.Errorf("inconsistent peer set")
		}
		p := peers[fields[0]]
		if _, exists := p["rx_bytes"]; exists {
			return nil, fmt.Errorf("duplicate transfer")
		}
		for _, value := range fields[1:] {
			if _, err := strconv.ParseUint(value, 10, 64); err != nil {
				return nil, err
			}
		}
		p["rx_bytes"], p["tx_bytes"] = fields[1], fields[2]
		result = append(result, p)
	}
	if len(result) != len(peers) {
		return nil, fmt.Errorf("inconsistent peer set")
	}
	return result, nil
}

func (s *Session) runtimeSnapshot() (map[string]any, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 12*time.Second)
	defer cancel()
	read := func(protocol string, args ...string) (string, error) {
		output, err := exec.CommandContext(ctx, tunnelTool(protocol), args...).Output()
		return strings.TrimSpace(string(output)), err
	}
	bundles, err := ownedRunningUsing(s.profile, read)
	if err != nil {
		return nil, err
	}
	if len(bundles) == 0 {
		return map[string]any{"status": "applied", "interface_state": "stopped", "peers": []any{}}, nil
	}
	if len(bundles) != 1 {
		return nil, fmt.Errorf("ambiguous owned interfaces")
	}
	b := bundles[0]
	actual, key, err := queryInterfaceUsing(b.Manifest.InterfaceName, b.Manifest.Protocol, read)
	if err != nil || actual == "" || key != b.Manifest.PublicKey {
		return nil, fmt.Errorf("interface ownership changed")
	}
	handshakes, err := read(b.Manifest.Protocol, "show", actual, "latest-handshakes")
	if err != nil {
		return nil, err
	}
	transfers, err := read(b.Manifest.Protocol, "show", actual, "transfer")
	if err != nil {
		return nil, err
	}
	peers, err := parsePeerSnapshot(handshakes, transfers)
	if err != nil {
		return nil, err
	}
	after, afterKey, err := queryInterfaceUsing(b.Manifest.InterfaceName, b.Manifest.Protocol, read)
	if err != nil || after != actual || afterKey != key {
		return nil, fmt.Errorf("interface changed during collection")
	}
	return map[string]any{"status": "applied", "interface_state": "running", "interface_public_key": key,
		"interface_name": actual, "tunnel_protocol": b.Manifest.Protocol, "awg_version": b.Manifest.AWGVersion, "config_sha256": b.Manifest.SHA256, "peers": peers}, nil
}
