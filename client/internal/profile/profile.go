package profile

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
)

type MQTTConfig struct {
	Host     string              `json:"host"`
	Port     int                 `json:"port"`
	TLS      bool                `json:"tls"`
	Username string              `json:"username"`
	Password string              `json:"password"`
	ClientID string              `json:"client_id"`
	Topics   map[string][]string `json:"topics"`
}

type ProfileMeta struct {
	ProfileID     string `json:"profile_id"`
	ServerURL     string `json:"server_url"`
	ConfigID      string `json:"config_id"`
	ConfigName    string `json:"config_name"`
	NodeID        string `json:"node_id"`
	NodeName      string `json:"node_name"`
	InterfaceName string `json:"interface_name"`
	Hostname      string `json:"hostname"`
	Platform      string `json:"platform"`
	ClientVersion string `json:"client_version"`
}

type Profile struct {
	Profile ProfileMeta `json:"profile"`
	MQTT    MQTTConfig  `json:"mqtt"`
}

type Summary struct {
	ProfileID      string
	ServerURL      string
	ConfigName     string
	NodeName       string
	MQTTHost       string
	MQTTPort       int
	MQTTTLS        bool
	ProfilePresent bool
	ProfileValid   bool
	DesiredPresent bool
}

func RootDir() (string, error) {
	switch runtime.GOOS {
	case "windows":
		base := os.Getenv("ProgramData")
		if base == "" {
			base = `C:\ProgramData`
		}
		return filepath.Join(base, "wg-free-mesh", "profiles"), nil
	case "darwin":
		return filepath.Join(string(filepath.Separator), "Library", "Application Support", "WG Free Mesh", "profiles"), nil
	default:
		return filepath.Join(string(filepath.Separator), "etc", "wg-free-mesh", "profiles"), nil
	}
}

func Save(p Profile, desiredConf string) error {
	root, err := RootDir()
	if err != nil {
		return err
	}
	dir := filepath.Join(root, p.Profile.ProfileID)
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return err
	}
	body, err := json.MarshalIndent(p, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(dir, "profile.json"), body, 0o600); err != nil {
		return err
	}
	return SaveConfig(p, desiredConf)
}

func SaveConfig(p Profile, desiredConf string) error {
	root, err := RootDir()
	if err != nil {
		return err
	}
	dir := filepath.Join(root, p.Profile.ProfileID)
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(dir, "desired.conf"), []byte(desiredConf), 0o600); err != nil {
		return err
	}
	iface := InterfaceName(p)
	if iface == "" {
		return nil
	}
	return os.WriteFile(filepath.Join(dir, iface+".conf"), []byte(desiredConf), 0o600)
}

func InterfaceName(p Profile) string {
	if p.Profile.InterfaceName != "" {
		return p.Profile.InterfaceName
	}
	if p.Profile.ProfileID != "" {
		return p.Profile.ProfileID
	}
	return ""
}

func ConfigPath(p Profile) (string, error) {
	root, err := RootDir()
	if err != nil {
		return "", err
	}
	iface := InterfaceName(p)
	if iface == "" {
		return "", fmt.Errorf("interface_name is required")
	}
	return filepath.Join(root, p.Profile.ProfileID, iface+".conf"), nil
}

func LoadAll() ([]Profile, error) {
	root, err := RootDir()
	if err != nil {
		return nil, err
	}
	entries, err := os.ReadDir(root)
	if os.IsNotExist(err) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	profiles := make([]Profile, 0, len(entries))
	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		body, err := os.ReadFile(filepath.Join(root, entry.Name(), "profile.json"))
		if err != nil {
			continue
		}
		var p Profile
		if json.Unmarshal(body, &p) == nil {
			profiles = append(profiles, p)
		}
	}
	return profiles, nil
}

func Summaries() ([]Summary, string, error) {
	root, err := RootDir()
	if err != nil {
		return nil, "", err
	}
	entries, err := os.ReadDir(root)
	if os.IsNotExist(err) {
		return nil, root, nil
	}
	if err != nil {
		return nil, root, err
	}
	summaries := make([]Summary, 0, len(entries))
	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		dir := filepath.Join(root, entry.Name())
		item := Summary{ProfileID: entry.Name()}
		body, err := os.ReadFile(filepath.Join(dir, "profile.json"))
		if err == nil {
			item.ProfilePresent = true
			var p Profile
			if json.Unmarshal(body, &p) == nil {
				item.ProfileValid = true
				item.ProfileID = p.Profile.ProfileID
				item.ServerURL = p.Profile.ServerURL
				item.ConfigName = p.Profile.ConfigName
				item.NodeName = p.Profile.NodeName
				item.MQTTHost = p.MQTT.Host
				item.MQTTPort = p.MQTT.Port
				item.MQTTTLS = p.MQTT.TLS
			}
		}
		if _, err := os.Stat(filepath.Join(dir, "desired.conf")); err == nil {
			item.DesiredPresent = true
		}
		summaries = append(summaries, item)
	}
	return summaries, root, nil
}

func Remove(profileID string) error {
	if profileID == "" {
		return fmt.Errorf("profile_id is required")
	}
	root, err := RootDir()
	if err != nil {
		return err
	}
	target := filepath.Clean(filepath.Join(root, profileID))
	if filepath.Dir(target) != filepath.Clean(root) {
		return fmt.Errorf("invalid profile_id: %s", profileID)
	}
	if _, err := os.Stat(target); os.IsNotExist(err) {
		return fmt.Errorf("profile %s is not bound on this machine", profileID)
	}
	return os.RemoveAll(target)
}

func RemoveAll() (int, error) {
	root, err := RootDir()
	if err != nil {
		return 0, err
	}
	entries, err := os.ReadDir(root)
	if os.IsNotExist(err) {
		return 0, nil
	}
	if err != nil {
		return 0, err
	}
	removed := 0
	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		if err := os.RemoveAll(filepath.Join(root, entry.Name())); err != nil {
			return removed, err
		}
		removed++
	}
	return removed, nil
}
