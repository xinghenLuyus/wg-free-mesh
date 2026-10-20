package profile

import (
	"fmt"
	"regexp"
	"runtime"
	"strings"
	"sync"
)

var nameMappingMu sync.Mutex
var interfaceNamePattern = regexp.MustCompile(`^[a-zA-Z0-9_=+.-]{1,15}$`)

// ResolveInterfaceName prepares a local mapping without changing the server name.
// Existing profiles without a mapping keep their old name until saved again.
func ResolveInterfaceName(p Profile) (Profile, error) {
	profiles, err := LoadAll()
	if err != nil {
		return Profile{}, err
	}
	return resolveInterfaceName(p, profiles)
}

func resolveInterfaceName(p Profile, profiles []Profile) (Profile, error) {
	raw := p.Profile.InterfaceName
	if raw == "" {
		raw = p.Profile.ProfileID
	}
	if raw == "" {
		return Profile{}, fmt.Errorf("interface_name is required")
	}
	names := make(map[string]string)
	for _, existing := range profiles {
		if existing.Profile.ProfileID == p.Profile.ProfileID {
			for original, actual := range existing.InterfaceNames {
				names[original] = actual
			}
		}
	}
	for original, actual := range p.InterfaceNames {
		names[original] = actual
	}
	actual := names[raw]
	if actual == "" {
		actual = raw
		if !interfaceNamePattern.MatchString(actual) {
			actual = artifactNameSegment(p.Profile.ConfigName)
			if len(actual) > 12 {
				actual = actual[:12]
			}
			actual = strings.Trim(actual, "-_.")
			if actual == "" {
				actual = "wireguard"
			}
			// Encoding/trimming can expose a Windows device name such as CON.
			base := strings.ToUpper(strings.SplitN(actual, ".", 2)[0])
			if base == "CON" || base == "PRN" || base == "AUX" || base == "NUL" || regexp.MustCompile(`^(COM|LPT)[1-9]$`).MatchString(base) {
				actual = "wg-" + actual
				if len(actual) > 12 {
					actual = actual[:12]
				}
			}
		}
	}
	if !interfaceNamePattern.MatchString(actual) {
		return Profile{}, fmt.Errorf("invalid local interface name for profile %s", p.Profile.ProfileID)
	}
	for _, existing := range profiles {
		if existing.Profile.ProfileID == p.Profile.ProfileID {
			continue
		}
		other := InterfaceName(existing)
		if actual == other || runtime.GOOS == "windows" && strings.EqualFold(actual, other) {
			return Profile{}, fmt.Errorf("local interface name %q conflicts with profile %s", actual, existing.Profile.ProfileID)
		}
	}
	names[raw] = actual
	p.InterfaceNames = names
	return p, nil
}

func artifactNameSegment(value string) string {
	var name strings.Builder
	for _, char := range strings.TrimSpace(value) {
		if char >= 'a' && char <= 'z' || char >= 'A' && char <= 'Z' || char >= '0' && char <= '9' || strings.ContainsRune("-_.", char) {
			name.WriteRune(char)
		} else {
			fmt.Fprintf(&name, "u%04x", char)
		}
	}
	return strings.Trim(name.String(), "-_.")
}
