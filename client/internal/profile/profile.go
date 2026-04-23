package profile

import (
	"encoding/json"
	"os"
	"path/filepath"
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
	Hostname      string `json:"hostname"`
	Platform      string `json:"platform"`
	ClientVersion string `json:"client_version"`
}

type Profile struct {
	Profile ProfileMeta `json:"profile"`
	MQTT    MQTTConfig  `json:"mqtt"`
}

func RootDir() (string, error) {
	base, err := os.UserConfigDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(base, "wfm", "profiles"), nil
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
	return os.WriteFile(filepath.Join(dir, "desired.conf"), []byte(desiredConf), 0o600)
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

