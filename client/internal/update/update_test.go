package update

import (
	"archive/zip"
	"os"
	"path/filepath"
	"testing"
)

func TestVersionOrdering(t *testing.T) {
	for _, test := range []struct {
		a, b string
		want int
	}{
		{"1.0.0-rc.9", "1.0.0-rc.10", -1}, {"1.0.0-rc.10", "1.0.0", -1},
		{"1.1.0-rc.1", "1.0.9", 1}, {"2.0.0", "1.99.99", 1}, {"1.0.0", "1.0.0", 0},
	} {
		got, err := CompareVersions(test.a, test.b)
		if err != nil || got != test.want {
			t.Fatalf("%s vs %s: %d %v", test.a, test.b, got, err)
		}
	}
	for _, version := range []string{"dev", "latest", "1.0", "1.0.0-rc.x", "01.0.0", "1.0.0+local"} {
		if _, err := CompareVersions(version, "1.0.0"); err == nil {
			t.Fatal("accepted invalid version", version)
		}
	}
}

func TestUpdateSelectors(t *testing.T) {
	for _, test := range []struct {
		args     []string
		local    bool
		selector string
	}{
		{nil, false, "1"}, {[]string{"--server"}, true, "1"}, {[]string{"--server", "2"}, true, "2"},
		{[]string{"cfg-node"}, false, "cfg-node"}, {[]string{"--server=cfg-node"}, true, "cfg-node"},
	} {
		local, selector, err := ParseArgs(test.args)
		if err != nil || local != test.local || selector != test.selector {
			t.Fatal(test, local, selector, err)
		}
	}
	for _, args := range [][]string{{"--local"}, {"--server", "--server"}, {"1", "2"}, {"--server="}} {
		if _, _, err := ParseArgs(args); err == nil {
			t.Fatal("accepted invalid arguments", args)
		}
	}
}

func TestUpdateTransportBoundary(t *testing.T) {
	for _, raw := range []string{"http://example.com", "https://user:password@example.com", "https://example.com/?token=x", "file:///tmp/package"} {
		if _, err := serverURL(raw); err == nil {
			t.Fatal("accepted unsafe server URL", raw)
		}
	}
	for _, raw := range []string{"http://localhost:8000", "http://127.0.0.1:8000", "http://[::1]:8000", "https://example.com"} {
		if _, err := serverURL(raw); err != nil {
			t.Fatal(raw, err)
		}
	}
}

func TestArchiveRejectsTraversal(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "package.zip")
	file, err := os.Create(path)
	if err != nil {
		t.Fatal(err)
	}
	writer := zip.NewWriter(file)
	entry, err := writer.Create("../escaped")
	if err != nil {
		t.Fatal(err)
	}
	if _, err = entry.Write([]byte("bad")); err != nil {
		t.Fatal(err)
	}
	if err = writer.Close(); err != nil {
		t.Fatal(err)
	}
	file.Close()
	if _, err = extractPackage(path, dir, "1.0.0"); err == nil {
		t.Fatal("accepted traversal")
	}
	if _, err = os.Stat(filepath.Join(filepath.Dir(dir), "escaped")); !os.IsNotExist(err) {
		t.Fatal("wrote outside package directory")
	}
}

func TestRecoveryLeavesAnUnchangedBinaryAlone(t *testing.T) {
	dir := t.TempDir()
	target := filepath.Join(dir, "original")
	if err := os.WriteFile(target, []byte("original bytes"), 0o600); err != nil {
		t.Fatal(err)
	}
	hash, err := fileHash(target)
	if err != nil {
		t.Fatal(err)
	}
	if err = restoreBinary(filepath.Join(dir, "backup-not-needed"), target, hash); err != nil {
		t.Fatal("unchanged destination must not require replacement", err)
	}
	actual, err := fileHash(target)
	if err != nil || actual != hash {
		t.Fatal("recovery modified intact bytes")
	}
}
