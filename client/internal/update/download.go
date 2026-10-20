package update

import (
	"archive/zip"
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	"wfm/client/internal/profile"
)

const githubRepository = "xinghenLuyus/wg-free-mesh"
const maxArchiveSize = 128 * 1024 * 1024

type artifact struct {
	Version       string `json:"version"`
	GOOS          string `json:"goos"`
	GOARCH        string `json:"goarch"`
	Source        string `json:"source"`
	Filename      string `json:"filename"`
	DownloadURL   string `json:"download_url"`
	ChecksumURL   string `json:"checksum_url"`
	DownloadPath  string `json:"download_path"`
	DownloadToken string `json:"download_token"`
	SHA256        string `json:"sha256"`
}

type packageManifest struct {
	Version string            `json:"version"`
	GOOS    string            `json:"goos"`
	GOARCH  string            `json:"goarch"`
	Files   map[string]string `json:"files"`
}

func serverURL(raw string) (*url.URL, error) {
	u, err := url.Parse(strings.TrimRight(raw, "/"))
	if err != nil {
		return nil, fmt.Errorf("invalid server URL")
	}
	if u.User != nil || u.RawQuery != "" || u.Fragment != "" || u.Host == "" {
		return nil, fmt.Errorf("invalid server URL")
	}
	if u.Scheme != "https" {
		ip := net.ParseIP(u.Hostname())
		if u.Scheme != "http" || (u.Hostname() != "localhost" && (ip == nil || !ip.IsLoopback())) {
			return nil, fmt.Errorf("updates require HTTPS (HTTP is permitted only on loopback)")
		}
	}
	return u, nil
}

func serverRequest(p profile.Profile, path string, body map[string]string) (artifact, error) {
	u, err := serverURL(p.Profile.ServerURL)
	if err != nil {
		return artifact{}, err
	}
	encoded, err := json.Marshal(body)
	if err != nil {
		return artifact{}, err
	}
	u.Path = strings.TrimRight(u.Path, "/") + "/api/client/v1/update/" + path
	req, err := http.NewRequest(http.MethodPost, u.String(), bytes.NewReader(encoded))
	if err != nil {
		return artifact{}, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.SetBasicAuth(p.MQTT.Username, p.MQTT.Password)
	client := &http.Client{Timeout: 12 * time.Minute, CheckRedirect: func(*http.Request, []*http.Request) error {
		return fmt.Errorf("authenticated update requests must not redirect")
	}}
	response, err := client.Do(req)
	if err != nil {
		return artifact{}, fmt.Errorf("update server request failed; check connectivity and TLS")
	}
	defer response.Body.Close()
	var envelope struct {
		Success bool     `json:"success"`
		Data    artifact `json:"data"`
		Error   struct {
			Message string `json:"message"`
		} `json:"error"`
	}
	if err = json.NewDecoder(io.LimitReader(response.Body, 1024*1024)).Decode(&envelope); err != nil {
		return artifact{}, fmt.Errorf("invalid update response (HTTP %d)", response.StatusCode)
	}
	if response.StatusCode != 200 || !envelope.Success {
		return artifact{}, fmt.Errorf("update server rejected request (HTTP %d): %s", response.StatusCode, envelope.Error.Message)
	}
	return envelope.Data, nil
}

func download(raw, path string, limit int64, sameOrigin bool) error {
	req, err := http.NewRequest(http.MethodGet, raw, nil)
	if err != nil {
		return fmt.Errorf("invalid download URL")
	}
	client := &http.Client{Timeout: 10 * time.Minute, CheckRedirect: func(req *http.Request, via []*http.Request) error {
		if len(via) > 8 {
			return fmt.Errorf("too many redirects")
		}
		if sameOrigin && (req.URL.Scheme != via[0].URL.Scheme || req.URL.Host != via[0].URL.Host) {
			return fmt.Errorf("local artifact must not redirect to another origin")
		}
		if via[0].URL.Scheme == "https" && req.URL.Scheme != "https" {
			return fmt.Errorf("insecure download redirect")
		}
		if via[0].URL.Scheme == "http" && (req.URL.Scheme != "http" || req.URL.Host != via[0].URL.Host) {
			return fmt.Errorf("unexpected local download redirect")
		}
		return nil
	}}
	response, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("download request failed; check connectivity and TLS")
	}
	defer response.Body.Close()
	if response.StatusCode != 200 {
		return fmt.Errorf("download failed (HTTP %d); no other source was selected", response.StatusCode)
	}
	file, err := os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
	if err != nil {
		return err
	}
	n, copyErr := io.Copy(file, io.LimitReader(response.Body, limit+1))
	if copyErr == nil {
		copyErr = file.Sync()
	}
	closeErr := file.Close()
	if copyErr != nil {
		return copyErr
	}
	if closeErr != nil {
		return closeErr
	}
	if n > limit {
		return fmt.Errorf("download exceeds size limit")
	}
	return nil
}

func fileHash(path string) (string, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer file.Close()
	digest := sha256.New()
	if _, err = io.Copy(digest, file); err != nil {
		return "", err
	}
	return hex.EncodeToString(digest.Sum(nil)), nil
}

func validHash(hash string) bool {
	decoded, err := hex.DecodeString(hash)
	return err == nil && len(decoded) == 32 && hash == strings.ToLower(hash)
}

func obtainPackage(p profile.Profile, a artifact, dir string, local bool) (packageManifest, error) {
	if a.Version == "" || a.GOOS != runtime.GOOS || a.GOARCH != runtime.GOARCH {
		return packageManifest{}, fmt.Errorf("artifact platform/version mismatch")
	}
	filename := fmt.Sprintf("wfm-client-%s-%s-v%s.zip", runtime.GOOS, runtime.GOARCH, a.Version)
	if a.Filename != filename {
		return packageManifest{}, fmt.Errorf("artifact filename mismatch")
	}
	var raw string
	if local {
		base, err := serverURL(p.Profile.ServerURL)
		if err != nil {
			return packageManifest{}, err
		}
		if a.Source != "local_build" || !strings.HasPrefix(a.DownloadPath, "/api/v1/tools/download/client-artifacts/") || strings.ContainsAny(a.DownloadPath, "?#") || a.DownloadToken == "" {
			return packageManifest{}, fmt.Errorf("invalid local artifact response")
		}
		base.Path = strings.TrimRight(base.Path, "/") + a.DownloadPath
		query := url.Values{}
		query.Set("download_token", a.DownloadToken)
		base.RawQuery = query.Encode()
		raw = base.String()
	} else {
		raw = "https://github.com/" + githubRepository + "/releases/download/v" + a.Version + "/" + filename
		if a.Source != "github_release" || a.DownloadURL != raw || a.ChecksumURL != raw+".sha256" {
			return packageManifest{}, fmt.Errorf("unexpected GitHub release URL")
		}
		checksumPath := filepath.Join(dir, "archive.sha256")
		if err := download(raw+".sha256", checksumPath, 4096, false); err != nil {
			return packageManifest{}, fmt.Errorf("%w; server build is available explicitly through wfmctl update --server %s", err, p.Profile.ProfileID)
		}
		body, err := os.ReadFile(checksumPath)
		if err != nil {
			return packageManifest{}, err
		}
		parts := strings.Fields(string(body))
		if len(parts) != 2 || parts[1] != filename {
			return packageManifest{}, fmt.Errorf("invalid release checksum file")
		}
		a.SHA256 = parts[0]
	}
	if !validHash(a.SHA256) {
		return packageManifest{}, fmt.Errorf("artifact checksum is missing or invalid")
	}
	archive := filepath.Join(dir, "package.zip")
	if err := download(raw, archive, maxArchiveSize, local); err != nil {
		return packageManifest{}, err
	}
	hash, err := fileHash(archive)
	if err != nil || hash != a.SHA256 {
		return packageManifest{}, fmt.Errorf("archive checksum mismatch")
	}
	return extractPackage(archive, dir, a.Version)
}

func extractPackage(archive, dir, version string) (packageManifest, error) {
	reader, err := zip.OpenReader(archive)
	if err != nil {
		return packageManifest{}, err
	}
	defer reader.Close()
	allowed := map[string]bool{"wfmctl" + suffix(): true, "wfm-agent" + suffix(): true, "package.json": true, "README.txt": true}
	seen := map[string]bool{}
	var total uint64
	for _, entry := range reader.File {
		total += entry.UncompressedSize64
		if total > 2*maxArchiveSize || ((entry.Name == "package.json" || entry.Name == "README.txt") && entry.UncompressedSize64 > 65536) {
			return packageManifest{}, fmt.Errorf("expanded archive exceeds size limit")
		}
		if !allowed[entry.Name] || seen[entry.Name] || !entry.Mode().IsRegular() || entry.UncompressedSize64 > maxArchiveSize {
			return packageManifest{}, fmt.Errorf("unexpected archive entry")
		}
		seen[entry.Name] = true
		stream, err := entry.Open()
		if err != nil {
			return packageManifest{}, err
		}
		path := filepath.Join(dir, entry.Name)
		mode := os.FileMode(0o600)
		if strings.HasPrefix(entry.Name, "wfm") {
			mode = 0o700
		}
		file, err := os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, mode)
		if err != nil {
			stream.Close()
			return packageManifest{}, err
		}
		n, err := io.Copy(file, io.LimitReader(stream, maxArchiveSize+1))
		stream.Close()
		if err == nil {
			err = file.Sync()
		}
		closeErr := file.Close()
		if err != nil {
			return packageManifest{}, err
		}
		if closeErr != nil {
			return packageManifest{}, closeErr
		}
		if n > maxArchiveSize {
			return packageManifest{}, fmt.Errorf("expanded file too large")
		}
	}
	var manifest packageManifest
	body, err := os.ReadFile(filepath.Join(dir, "package.json"))
	if err != nil {
		return manifest, err
	}
	if err = json.Unmarshal(body, &manifest); err != nil {
		return manifest, err
	}
	if manifest.Version != version || manifest.GOOS != runtime.GOOS || manifest.GOARCH != runtime.GOARCH || len(manifest.Files) != 2 {
		return manifest, fmt.Errorf("package metadata mismatch")
	}
	for _, name := range []string{"wfmctl" + suffix(), "wfm-agent" + suffix()} {
		hash, err := fileHash(filepath.Join(dir, name))
		if err != nil || !validHash(manifest.Files[name]) || hash != manifest.Files[name] {
			return manifest, fmt.Errorf("binary checksum mismatch: %s", name)
		}
		program := "ctl"
		if strings.HasPrefix(name, "wfm-agent") {
			program = "agent"
		}
		actual, err := binaryVersion(filepath.Join(dir, name), program, runtime.GOOS, runtime.GOARCH)
		if err != nil {
			return manifest, err
		}
		if actual != version {
			return manifest, fmt.Errorf("binary version mismatch")
		}
	}
	return manifest, nil
}

func suffix() string {
	if runtime.GOOS == "windows" {
		return ".exe"
	}
	return ""
}
