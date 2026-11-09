package mqtt

import "testing"

func TestSnapshotParsing(t *testing.T) {
	rows, err := parsePeerSnapshot("a\t0\nb\t1720000000", "a\t0\t18446744073709551615\nb\t9007199254740993\t2")
	if err != nil || len(rows) != 2 || rows[0]["tx_bytes"] != "18446744073709551615" || rows[1]["rx_bytes"] != "9007199254740993" {
		t.Fatal(rows, err)
	}
	for _, pair := range [][2]string{{"a -1", "a 1 2"}, {"a 1", "b 1 2"}, {"a 1", ""}, {"a 1\na 2", "a 1 2"}, {"a 1", "a 1 2\na 3 4"}, {"a 1", "a 1;whoami 2"}} {
		if _, err := parsePeerSnapshot(pair[0], pair[1]); err == nil {
			t.Fatal("accepted malformed snapshot", pair)
		}
	}
	rows, err = parsePeerSnapshot("", "")
	if err != nil || len(rows) != 0 {
		t.Fatal(rows, err)
	}
}

func TestOnlyCurrentInterfaceIsStrictBoolean(t *testing.T) {
	for _, v := range []any{"true", "wg0;id", []string{"show"}, 1, nil} {
		if _, ok := currentInterfaceOnly(map[string]any{"current_interface_only": v}); ok {
			t.Fatal("accepted", v)
		}
	}
	if only, ok := currentInterfaceOnly(map[string]any{}); only || !ok {
		t.Fatal("default changed")
	}
	if only, ok := currentInterfaceOnly(map[string]any{"current_interface_only": true}); !only || !ok {
		t.Fatal("true rejected")
	}
}

func TestManualShowDefaultKeepsRawOutput(t *testing.T) {
	previous := showAllInterfaces
	t.Cleanup(func() { showAllInterfaces = previous })
	showAllInterfaces = func(protocol string) (string, error) {
		if protocol != "wireguard" {
			t.Fatal(protocol)
		}
		return "interface: wg0\n  complete human readable output", nil
	}
	output, err := (&Session{}).showInformation("wireguard", false)
	if err != nil || output != "interface: wg0\n  complete human readable output" {
		t.Fatal(output, err)
	}
}
