package profile

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

const bundleTestConfig = "[Interface]\nPrivateKey = AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=\nAddress = 10.0.0.1/32\n"

func bundleTestProfile() Profile {
	return Profile{Profile: ProfileMeta{ProfileID: "cfg-node", ConfigID: "cfg", NodeID: "node", InterfaceName: "home-a"}}
}

func TestBundleIntegrityAndOwnership(t *testing.T) {
	p := bundleTestProfile()
	m, err := NewManifest(p, bundleTestConfig, "wireguard", "4", "")
	if err != nil {
		t.Fatal(err)
	}
	dir := filepath.Join(t.TempDir(), "config")
	if err = WriteBundle(dir, m, bundleTestConfig); err != nil {
		t.Fatal(err)
	}
	b, err := ReadBundle(dir, p)
	if err != nil || b.Manifest.PublicKey == "" || b.Manifest.Protocol != "wireguard" {
		t.Fatalf("invalid bundle: %+v %v", b, err)
	}
	other := p
	other.Profile.NodeID = "other"
	if _, err = ReadBundle(dir, other); err == nil {
		t.Fatal("accepted another binding's bundle")
	}
	if err = os.WriteFile(b.ConfigPath(), []byte(bundleTestConfig+"MTU = 1280\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err = ReadBundle(dir, p); err == nil {
		t.Fatal("accepted a corrupt bundle")
	}
}

func TestLegacyMigrationPreservesOriginalAndIsRepeatable(t *testing.T) {
	p := bundleTestProfile()
	dir := t.TempDir()
	path := filepath.Join(dir, "home-a.conf")
	if err := os.WriteFile(path, []byte(bundleTestConfig), 0o600); err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 2; i++ {
		if err := migrateDirectory(dir, p); err != nil {
			t.Fatal(err)
		}
	}
	b, err := ReadBundle(filepath.Join(dir, "config"), p)
	if err != nil {
		t.Fatal(err)
	}
	if b.StopPath() != path {
		t.Fatal("migration lost the original down-hook path")
	}
	original, err := os.ReadFile(path)
	if err != nil || string(original) != bundleTestConfig {
		t.Fatal("migration changed the original config")
	}
}

func TestManifestRecordsAWGToolchain(t *testing.T) {
	p := bundleTestProfile()
	text := bundleTestConfig + "Jc = 4\nHeaderProtectionKey = example\n"
	m, err := NewManifest(p, text, "", "", "")
	if err != nil || m.Protocol != "amneziawg_2" || m.Toolchain != "amneziawg" {
		t.Fatalf("lost legacy AWG identity: %+v %v", m, err)
	}
	if _, err = NewManifest(p, text, "wireguard", "", ""); err == nil {
		t.Fatal("accepted AWG parameters as WireGuard")
	}
	if _, err = NewManifest(p, strings.ReplaceAll(bundleTestConfig, "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=", "invalid"), "wireguard", "", ""); err == nil {
		t.Fatal("accepted invalid private key")
	}
}

func TestBundleRejectsPathTraversal(t *testing.T) {
	p := bundleTestProfile()
	m, err := NewManifest(p, bundleTestConfig, "wireguard", "", "")
	if err != nil {
		t.Fatal(err)
	}
	m.File = "../escape.conf"
	if err = WriteBundle(t.TempDir(), m, bundleTestConfig); err == nil {
		t.Fatal("accepted traversal")
	}
	if _, err = profileDirectory(t.TempDir(), "../outside"); err == nil {
		t.Fatal("accepted invalid binding directory")
	}
}
