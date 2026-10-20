package profile

import (
	"crypto/ecdh"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

// Manifest describes a complete generation, independently of the latest server payload.
type Manifest struct {
	ConfigID      string `json:"config_id"`
	NodeID        string `json:"node_id"`
	Protocol      string `json:"tunnel_protocol"`
	AWGVersion    string `json:"awg_version,omitempty"`
	Toolchain     string `json:"toolchain"`
	ServerName    string `json:"server_name"`
	InterfaceName string `json:"interface_name"`
	File          string `json:"file"`
	PublicKey     string `json:"public_key"`
	Version       string `json:"version,omitempty"`
	SHA256        string `json:"sha256"`
	ReceivedAt    string `json:"received_at"`
	// LegacyFile preserves the original path for down hooks until the first replacement.
	LegacyFile string `json:"legacy_file,omitempty"`
}

type Bundle struct {
	Manifest Manifest
	Dir      string
}

func Directory(p Profile) (string, error) {
	root, err := RootDir()
	if err != nil {
		return "", err
	}
	return profileDirectory(root, p.Profile.ProfileID)
}

func profileDirectory(root, id string) (string, error) {
	if id == "" || filepath.Base(id) != id || id == "." || id == ".." {
		return "", fmt.Errorf("invalid profile_id")
	}
	return filepath.Join(root, id), nil
}

func NewManifest(p Profile, text, protocol, version, awgVersion string) (Manifest, error) {
	protocolFromText := "wireguard"
	privateKey := ""
	inInterface := false
	for _, line := range strings.Split(text, "\n") {
		line = strings.TrimSpace(strings.SplitN(line, "#", 2)[0])
		if strings.HasPrefix(line, "[") {
			inInterface = strings.EqualFold(line, "[Interface]")
			continue
		}
		if !inInterface {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		if len(parts) != 2 {
			continue
		}
		key, value := strings.ToLower(strings.TrimSpace(parts[0])), strings.TrimSpace(parts[1])
		if key == "privatekey" {
			privateKey = value
		}
		switch key {
		case "jc", "jmin", "jmax", "s1", "s2", "s3", "s4", "s5", "h1", "h2", "h3", "h4", "i1", "i2", "i3", "i4", "i5", "headerprotectionkey", "randomtrailers", "contentpaddingaddition", "rekeyaftertime", "rekeytimeout", "rejectaftertime", "keepalivetimeout", "maxhandshakeattempts", "disablecookies":
			protocolFromText = "amneziawg_2"
		}
	}
	if protocol == "" {
		protocol = protocolFromText
	}
	if protocol != "wireguard" && protocol != "amneziawg_2" {
		return Manifest{}, fmt.Errorf("unsupported tunnel protocol")
	}
	if awgVersion != "" && awgVersion != "1.5" && awgVersion != "2.0" && awgVersion != "3.1" {
		return Manifest{}, fmt.Errorf("unsupported AWG version")
	}
	if protocol == "wireguard" && protocolFromText != protocol {
		return Manifest{}, fmt.Errorf("AWG parameters in WireGuard configuration")
	}
	key, err := base64.StdEncoding.DecodeString(privateKey)
	if err != nil {
		return Manifest{}, fmt.Errorf("invalid interface private key")
	}
	secret, err := ecdh.X25519().NewPrivateKey(key)
	if err != nil {
		return Manifest{}, fmt.Errorf("invalid interface private key")
	}
	name := InterfaceName(p)
	// Legacy names may exceed the new alias limit; retain them only for migration.
	if name == "" || filepath.Base(name) != name || strings.ContainsAny(name, "/\\") {
		return Manifest{}, fmt.Errorf("invalid interface name")
	}
	digest := sha256.Sum256([]byte(text))
	toolchain := "wireguard"
	if protocol == "amneziawg_2" {
		toolchain = "amneziawg"
	}
	return Manifest{ConfigID: p.Profile.ConfigID, NodeID: p.Profile.NodeID, Protocol: protocol, AWGVersion: awgVersion,
		Toolchain: toolchain, ServerName: p.Profile.InterfaceName, InterfaceName: name, File: name + ".conf",
		PublicKey: base64.StdEncoding.EncodeToString(secret.PublicKey().Bytes()), Version: version,
		SHA256: hex.EncodeToString(digest[:]), ReceivedAt: time.Now().UTC().Format(time.RFC3339Nano)}, nil
}

func (b Bundle) ConfigPath() string { return filepath.Join(b.Dir, b.Manifest.File) }

func (b Bundle) StopPath() string {
	if b.Manifest.LegacyFile != "" {
		return filepath.Join(filepath.Dir(b.Dir), b.Manifest.LegacyFile)
	}
	return b.ConfigPath()
}

func AtomicJSON(path string, value any) error {
	body, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	return atomicWrite(path, body)
}

func atomicWrite(path string, body []byte) error {
	f, err := os.CreateTemp(filepath.Dir(path), ".write-*")
	if err != nil {
		return err
	}
	defer os.Remove(f.Name())
	if _, err = f.Write(body); err != nil {
		f.Close()
		return err
	}
	if err = f.Sync(); err != nil {
		f.Close()
		return err
	}
	if err = f.Close(); err != nil {
		return err
	}
	if err = os.Rename(f.Name(), path); err != nil {
		return err
	}
	return syncDirectory(filepath.Dir(path))
}

func syncDirectory(dir string) error {
	if runtime.GOOS == "windows" {
		return nil
	}
	f, err := os.Open(dir)
	if err != nil {
		return err
	}
	defer f.Close()
	return f.Sync()
}

func WriteBundle(dir string, m Manifest, text string) error {
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return err
	}
	if filepath.Base(m.File) != m.File || m.File != m.InterfaceName+".conf" {
		return fmt.Errorf("invalid bundle file")
	}
	if err := atomicWrite(filepath.Join(dir, m.File), []byte(text)); err != nil {
		return err
	}
	return AtomicJSON(filepath.Join(dir, "manifest.json"), m)
}

func ReadBundle(dir string, p Profile) (Bundle, error) {
	body, err := os.ReadFile(filepath.Join(dir, "manifest.json"))
	if err != nil {
		return Bundle{}, err
	}
	var m Manifest
	if err = json.Unmarshal(body, &m); err != nil {
		return Bundle{}, err
	}
	if m.ConfigID != p.Profile.ConfigID || m.NodeID != p.Profile.NodeID {
		return Bundle{}, fmt.Errorf("bundle belongs to another binding")
	}
	if m.Protocol != "wireguard" && m.Protocol != "amneziawg_2" {
		return Bundle{}, fmt.Errorf("invalid bundle protocol")
	}
	if m.File != m.InterfaceName+".conf" || filepath.Base(m.File) != m.File || strings.ContainsAny(m.File, "/\\") {
		return Bundle{}, fmt.Errorf("invalid bundle path")
	}
	if m.LegacyFile != "" && (filepath.Base(m.LegacyFile) != m.LegacyFile || strings.ContainsAny(m.LegacyFile, "/\\")) {
		return Bundle{}, fmt.Errorf("invalid legacy path")
	}
	text, err := os.ReadFile(filepath.Join(dir, m.File))
	if err != nil {
		return Bundle{}, err
	}
	copy := p
	copy.Profile.InterfaceName = m.InterfaceName
	copy.InterfaceNames = nil
	actual, err := NewManifest(copy, string(text), m.Protocol, m.Version, m.AWGVersion)
	if err != nil {
		return Bundle{}, err
	}
	if actual.SHA256 != m.SHA256 || actual.PublicKey != m.PublicKey || actual.Toolchain != m.Toolchain {
		return Bundle{}, fmt.Errorf("bundle integrity check failed")
	}
	return Bundle{Manifest: m, Dir: dir}, nil
}

func Bundles(p Profile) ([]Bundle, error) {
	dir, err := Directory(p)
	if err != nil {
		return nil, err
	}
	var bundles []Bundle
	for _, name := range []string{"config", "config.old", "config.old2"} {
		b, err := ReadBundle(filepath.Join(dir, name), p)
		if os.IsNotExist(err) {
			// A directory without a manifest is corruption, not an absent generation.
			if _, statErr := os.Stat(filepath.Join(dir, name)); os.IsNotExist(statErr) {
				continue
			}
		}
		if err != nil {
			return nil, fmt.Errorf("read %s: %w", name, err)
		}
		bundles = append(bundles, b)
	}
	return bundles, nil
}

// LegacyBundles are read-only recovery candidates. Never infer their recency from mtime.
func LegacyBundles(p Profile) ([]Bundle, error) {
	dir, err := Directory(p)
	if err != nil {
		return nil, err
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	var result []Bundle
	for _, entry := range entries {
		if entry.IsDir() || filepath.Ext(entry.Name()) != ".conf" || entry.Name() == "desired.conf" {
			continue
		}
		text, err := os.ReadFile(filepath.Join(dir, entry.Name()))
		if err != nil {
			return nil, err
		}
		if strings.TrimSpace(string(text)) == "" {
			continue
		}
		old := p
		old.Profile.InterfaceName = strings.TrimSuffix(entry.Name(), ".conf")
		old.InterfaceNames = nil
		m, err := NewManifest(old, string(text), "", "", "")
		if err != nil {
			return nil, fmt.Errorf("invalid legacy config %s: %w", entry.Name(), err)
		}
		result = append(result, Bundle{Manifest: m, Dir: dir})
	}
	return result, nil
}

func Migrate(p Profile) error {
	dir, err := Directory(p)
	if err != nil {
		return err
	}
	return migrateDirectory(dir, p)
}

func migrateDirectory(dir string, p Profile) error {
	var err error
	if _, err = os.Stat(filepath.Join(dir, "config")); err == nil {
		_, err = ReadBundle(filepath.Join(dir, "config"), p)
		return err
	} else if !os.IsNotExist(err) {
		return err
	}
	path := filepath.Join(dir, InterfaceName(p)+".conf")
	text, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return nil
	}
	if err != nil {
		return err
	}
	if strings.TrimSpace(string(text)) == "" {
		return nil
	}
	m, err := NewManifest(p, string(text), "", "", "")
	if err != nil {
		return err
	}
	m.LegacyFile = filepath.Base(path)
	// Build off to the side; a crash cannot leave a half-migrated current directory.
	tmp := filepath.Join(dir, ".config.migrating")
	if err = WriteBundle(tmp, m, string(text)); err != nil {
		return err
	}
	if err = os.Rename(tmp, filepath.Join(dir, "config")); err != nil {
		return err
	}
	return syncDirectory(dir)
}

func SaveMetadata(p Profile) error {
	dir, err := Directory(p)
	if err != nil {
		return err
	}
	return AtomicJSON(filepath.Join(dir, "profile.json"), p)
}

func Load(id string) (Profile, error) {
	root, err := RootDir()
	if err != nil {
		return Profile{}, err
	}
	dir, err := profileDirectory(root, id)
	if err != nil {
		return Profile{}, err
	}
	body, err := os.ReadFile(filepath.Join(dir, "profile.json"))
	if err != nil {
		return Profile{}, err
	}
	var p Profile
	if err = json.Unmarshal(body, &p); err != nil {
		return Profile{}, err
	}
	if p.Profile.ProfileID != id {
		return Profile{}, fmt.Errorf("profile identity mismatch")
	}
	return p, nil
}
