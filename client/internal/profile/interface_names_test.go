package profile

import (
	"encoding/json"
	"strings"
	"testing"
)

func TestInterfaceNameMapping(t *testing.T) {
	for _, tt := range []struct {
		name, config, raw, want string
	}{
		{"short", "home", "home-node", "home-node"},
		{"limit", "home", "home-1234567890", "home-1234567890"},
		{"fifteen", "home", "home-12345678901", "home-12345678901"},
		{"long node", "home", "home-123456789012", "home"},
		{"long config", "abcdefghijklmnop", "abcdefghijklmnop-node", "abcdefghijkl"},
		{"unicode node", "home", "home-u5317u4eacu8282u70b9", "home"},
		{"encoded config", "a=+b", "au003du002bb-verylongnode", "au003du002bb"},
		{"empty config", "", "very-long-interface-name", "wireguard"},
		{"reserved config segment", "CON---", "CON-very-long-node-name", "wg-CON"},
	} {
		t.Run(tt.name, func(t *testing.T) {
			p := Profile{Profile: ProfileMeta{ProfileID: "p1", ConfigName: tt.config, InterfaceName: tt.raw}}
			mapped, err := resolveInterfaceName(p, nil)
			if err != nil {
				t.Fatal(err)
			}
			if got := InterfaceName(mapped); got != tt.want || len(got) > 15 {
				t.Fatalf("got %q, want %q", got, tt.want)
			}
			if mapped.Profile.InterfaceName != tt.raw || p.InterfaceNames != nil {
				t.Fatal("server name and original profile must remain unchanged")
			}
			data, err := json.Marshal(mapped)
			if err != nil {
				t.Fatal(err)
			}
			var restored Profile
			if err := json.Unmarshal(data, &restored); err != nil {
				t.Fatal(err)
			}
			if InterfaceName(restored) != tt.want {
				t.Fatal("mapping lost after JSON round trip")
			}
		})
	}
}

func TestInterfaceRenamePreservesOldMapping(t *testing.T) {
	old := Profile{Profile: ProfileMeta{ProfileID: "p1", ConfigName: "home", InterfaceName: "home-old-name-too-long"}}
	if InterfaceName(old) != old.Profile.InterfaceName {
		t.Fatal("legacy interfaces must not be renamed on read")
	}
	current, err := resolveInterfaceName(old, nil)
	if err != nil {
		t.Fatal(err)
	}
	next := current
	next.Profile.InterfaceName = "home-new-name-too-long"
	next, err = resolveInterfaceName(next, []Profile{current})
	if err != nil {
		t.Fatal(err)
	}
	if len(current.InterfaceNames) != 1 || len(next.InterfaceNames) != 2 {
		t.Fatal("preparing the next mapping must not mutate the old mapping")
	}
	if InterfaceName(next) != "home" || next.InterfaceNames[current.Profile.InterfaceName] != "home" {
		t.Fatal("both original names must retain their local mappings")
	}
	if _, err := resolveInterfaceName(current, []Profile{next}); err != nil {
		t.Fatal("a profile may reuse its own alias", err)
	}
	other := Profile{Profile: ProfileMeta{ProfileID: "p2", ConfigName: "home", InterfaceName: "home-other-name-too-long"}}
	if _, err := resolveInterfaceName(other, []Profile{next}); err == nil || !strings.Contains(err.Error(), "conflicts") {
		t.Fatal("another profile must not reuse an active local name")
	}
}
