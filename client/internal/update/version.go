package update

import (
	"debug/buildinfo"
	"fmt"
	"regexp"
	"strconv"
	"strings"
)

var versionPattern = regexp.MustCompile(`^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-rc\.(0|[1-9][0-9]*))?$`)

func CompareVersions(a, b string) (int, error) {
	parse := func(text string) ([4]uint64, error) {
		var result [4]uint64
		parts := versionPattern.FindStringSubmatch(text)
		if parts == nil {
			return result, fmt.Errorf("unsupported version %q", text)
		}
		for i := 0; i < 3; i++ {
			value, err := strconv.ParseUint(parts[i+1], 10, 64)
			if err != nil {
				return result, err
			}
			result[i] = value
		}
		result[3] = ^uint64(0)
		if parts[4] != "" {
			value, err := strconv.ParseUint(parts[4], 10, 64)
			if err != nil || value == ^uint64(0) {
				return result, fmt.Errorf("invalid prerelease version")
			}
			result[3] = value
		}
		return result, nil
	}
	x, err := parse(a)
	if err != nil {
		return 0, err
	}
	y, err := parse(b)
	if err != nil {
		return 0, err
	}
	for i := range x {
		if x[i] < y[i] {
			return -1, nil
		}
		if x[i] > y[i] {
			return 1, nil
		}
	}
	return 0, nil
}

// Inspect build metadata instead of executing an old agent with an unsupported flag.
// Older agents interpret unknown arguments as a request to run the agent.
func binaryVersion(path, program, goos, goarch string) (string, error) {
	info, err := buildinfo.ReadFile(path)
	if err != nil {
		return "", err
	}
	if info.Path != "wfm/client/cmd/"+program {
		return "", fmt.Errorf("unexpected program at %s", path)
	}
	values := map[string]string{}
	for _, setting := range info.Settings {
		values[setting.Key] = setting.Value
	}
	if values["GOOS"] != goos || values["GOARCH"] != goarch {
		return "", fmt.Errorf("installed program platform does not match %s/%s", goos, goarch)
	}
	fields := strings.Fields(values["-ldflags"])
	for _, field := range fields {
		if strings.HasPrefix(field, "wfm/client/internal/bind.Version=") {
			version := strings.TrimPrefix(field, "wfm/client/internal/bind.Version=")
			if _, err = CompareVersions(version, version); err != nil {
				return "", err
			}
			return version, nil
		}
	}
	return "", fmt.Errorf("version metadata is missing from %s; install a versioned release first", path)
}
