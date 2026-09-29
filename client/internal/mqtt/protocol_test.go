package mqtt

import "testing"

func TestTunnelProtocolCompatibility(t *testing.T) {
	for _, value := range []string{"amneziawg", "amneziawg_2"} {
		payload := map[string]any{"tunnel_protocol": value}
		if err := validateTunnelPayload(payload); err != nil {
			t.Fatal(err)
		}
		if tunnelProtocolFromPayload(payload) != "amneziawg_2" || normalizeTunnelProtocol(value) != "amneziawg_2" {
			t.Fatalf("protocol %s must select AWG tools", value)
		}
		for _, version := range []string{"1.5", "2.0", "3.1"} {
			payload["awg_version"] = version
			if err := validateTunnelPayload(payload); err != nil {
				t.Fatal(err)
			}
		}
	}
	if err := validateTunnelPayload(map[string]any{}); err != nil {
		t.Fatal("legacy messages without a protocol/version must remain valid", err)
	}
}

func TestUnsupportedTunnelPayload(t *testing.T) {
	for _, payload := range []map[string]any{
		{"tunnel_protocol": "unknown"},
		{"previous_tunnel_protocol": "unknown"},
		{"tunnel_protocol": "amneziawg", "awg_version": "3.0"},
	} {
		if validateTunnelPayload(payload) == nil {
			t.Fatalf("expected rejection: %v", payload)
		}
	}
}
