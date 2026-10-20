package mqtt

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"time"

	pahomqtt "github.com/eclipse/paho.golang/paho"

	"wfm/client/internal/bind"
	"wfm/client/internal/profile"
)

type Envelope struct {
	Type      string         `json:"type"`
	RequestID string         `json:"request_id"`
	ConfigID  string         `json:"config_id"`
	NodeID    string         `json:"node_id"`
	BootID    string         `json:"boot_id"`
	SessionID string         `json:"session_id"`
	SentAt    string         `json:"sent_at"`
	Payload   map[string]any `json:"payload"`
}

type Session struct {
	profile     profile.Profile
	bootID      string
	sessionID   string
	client      *pahomqtt.Client
	logger      io.Writer
	reconnect   bool
	connected   bool
	lifecycleMu *sync.Mutex
	configID    string
	nodeID      string
	profileID   string
}

func NewSession(p profile.Profile, logger io.Writer, reconnect bool) *Session {
	now := time.Now().UnixNano()
	return &Session{
		profile:     p,
		lifecycleMu: bindingLock(p),
		configID:    p.Profile.ConfigID,
		nodeID:      p.Profile.NodeID,
		profileID:   p.Profile.ProfileID,
		bootID:      fmt.Sprintf("boot-%d", now),
		sessionID:   fmt.Sprintf("session-%d", now),
		logger:      logger,
		reconnect:   reconnect,
	}
}

func (s *Session) Connected() bool {
	return s.connected
}

func (s *Session) Run(ctx context.Context) error {
	lock := s.lifecycleMu
	lock.Lock()
	latest, recoveryErr := profile.Load(s.profile.Profile.ProfileID)
	if recoveryErr == nil {
		s.profile = latest
		recoveryErr = s.resumeTransition(false)
	}
	if recoveryErr == nil {
		recoveryErr = profile.Migrate(s.profile)
	}
	lock.Unlock()
	if recoveryErr != nil {
		s.logf("configuration recovery failed: %v", recoveryErr)
	}
	conn, err := s.dial()
	if err != nil {
		return err
	}
	defer conn.Close()
	ready := make(chan struct{})
	runCtx, cancelRun := context.WithCancel(ctx)
	defer cancelRun()
	will, _ := json.Marshal(s.envelope("event", "", map[string]any{
		"level":   "info",
		"event":   "offline",
		"message": "Client disconnected with will message.",
	}))
	client := pahomqtt.NewClient(pahomqtt.ClientConfig{
		Conn: conn,
		Router: pahomqtt.NewSingleHandlerRouter(func(m *pahomqtt.Publish) {
			select {
			case <-ready:
			case <-runCtx.Done():
				return
			}
			s.handleMessage(m)
		}),
		OnClientError: func(err error) {
			_ = err
		},
		OnServerDisconnect: func(d *pahomqtt.Disconnect) {
			_ = d
		},
	})
	cp := &pahomqtt.Connect{
		KeepAlive:  60,
		ClientID:   s.profile.MQTT.ClientID,
		CleanStart: false,
		WillMessage: &pahomqtt.WillMessage{
			Topic:   s.topic("event"),
			Payload: will,
			QoS:     1,
			Retain:  false,
		},
	}
	if s.profile.MQTT.Username != "" {
		cp.UsernameFlag = true
		cp.Username = s.profile.MQTT.Username
	}
	if s.profile.MQTT.Password != "" {
		cp.PasswordFlag = true
		cp.Password = []byte(s.profile.MQTT.Password)
	}
	if ack, err := client.Connect(ctx, cp); err != nil {
		return err
	} else if ack.ReasonCode != 0 {
		return fmt.Errorf("mqtt connect rejected: %d", ack.ReasonCode)
	}
	s.client = client
	close(ready)
	if recoveryErr != nil {
		_ = s.publishEvent("config_recovery", fmt.Sprintf("Configuration recovery failed: %v", recoveryErr))
	}
	if err := s.subscribe(ctx); err != nil {
		return err
	}
	if err := s.publishEvent("online", "Client connected and MQTT session established."); err != nil {
		return fmt.Errorf("publish online event failed: %w", err)
	}
	if err := s.publishHeartbeat(); err != nil {
		return fmt.Errorf("publish heartbeat failed: %w", err)
	}
	s.connected = true
	lock.Lock()
	if s.reconnect {
		s.logf("mqtt reconnected profile=%s host=%s port=%d tls=%t", s.profile.Profile.ProfileID, s.profile.MQTT.Host, s.profile.MQTT.Port, s.profile.MQTT.TLS)
	} else {
		s.logf("mqtt connected profile=%s host=%s port=%d tls=%t", s.profile.Profile.ProfileID, s.profile.MQTT.Host, s.profile.MQTT.Port, s.profile.MQTT.TLS)
	}
	lock.Unlock()
	ticker := time.NewTicker(30 * time.Minute)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return nil
		case <-client.Done():
			s.logf("mqtt disconnected profile=%s reason=connection_closed", s.profileID)
			return fmt.Errorf("mqtt connection closed")
		case <-ticker.C:
			if err := s.publishHeartbeat(); err != nil {
				s.logf("mqtt disconnected profile=%s reason=%v", s.profileID, err)
				return fmt.Errorf("publish heartbeat failed: %w", err)
			}
		}
	}
}

func (s *Session) dial() (net.Conn, error) {
	addr := net.JoinHostPort(s.profile.MQTT.Host, strconv.Itoa(s.profile.MQTT.Port))
	if s.profile.MQTT.TLS {
		if strings.TrimSpace(s.profile.MQTT.CACert) == "" {
			return nil, fmt.Errorf("mqtt tls ca certificate is missing, re-bind this client")
		}
		roots := x509.NewCertPool()
		if !roots.AppendCertsFromPEM([]byte(s.profile.MQTT.CACert)) {
			return nil, fmt.Errorf("invalid mqtt tls ca certificate, re-bind this client")
		}
		return tls.Dial("tcp", addr, &tls.Config{
			MinVersion: tls.VersionTLS12,
			RootCAs:    roots,
			ServerName: s.profile.MQTT.Host,
		})
	}
	return net.DialTimeout("tcp", addr, 10*time.Second)
}

func (s *Session) subscribe(ctx context.Context) error {
	_, err := s.client.Subscribe(ctx, &pahomqtt.Subscribe{
		Subscriptions: []pahomqtt.SubscribeOptions{
			{Topic: s.topic("config/push"), QoS: 1},
			{Topic: s.topic("control"), QoS: 1},
			{Topic: s.topic("detect"), QoS: 1},
			{Topic: s.topic("info"), QoS: 1},
		},
	})
	return err
}

func (s *Session) handleMessage(m *pahomqtt.Publish) {
	lock := s.lifecycleMu
	lock.Lock()
	defer lock.Unlock()
	var env Envelope
	_ = json.Unmarshal(m.Payload, &env)
	if err := validateTunnelPayload(env.Payload); err != nil {
		for _, kind := range []string{"detect", "info", "control", "config/push"} {
			if m.Topic == s.topic(kind) {
				_ = s.publish(kind+"/ack", s.envelope(kind+"/ack", env.RequestID, map[string]any{"status": "failed", "message": err.Error()}))
				return
			}
		}
	}
	switch m.Topic {
	case s.topic("detect"):
		wgOnline, statusErr := s.tunnelStatus()
		status, message := "applied", "Detect completed."
		if statusErr != nil {
			status, message = "failed", statusErr.Error()
		}
		_ = s.publishEvent("detect", "Server detect command received.")
		_ = s.publish("detect/ack", s.envelope("detect/ack", env.RequestID, map[string]any{
			"status":         status,
			"client_online":  true,
			"wg_online":      wgOnline,
			"platform":       runtime.GOOS,
			"client_version": bind.Version,
			"message":        message,
		}))
	case s.topic("info"):
		tunnelProtocol := tunnelProtocolFromPayload(env.Payload)
		action := fmt.Sprint(env.Payload["action"])
		if action == "" || action == "<nil>" {
			action = "wg_show"
		}
		output, err := runWGShow(tunnelProtocol)
		level := "info"
		message := "wg completed."
		status := "applied"
		if err != nil {
			level = "error"
			message = err.Error()
			status = "failed"
		}
		_ = s.publish("event", s.envelope("event", "", map[string]any{
			"level":      level,
			"event":      "command_output",
			"request_id": env.RequestID,
			"action":     action,
			"stream":     "stdout",
			"message":    message,
			"output":     output,
		}))
		_ = s.publish("info/ack", s.envelope("info/ack", env.RequestID, map[string]any{
			"status":  status,
			"action":  action,
			"message": message,
		}))
	case s.topic("control"):
		action := fmt.Sprint(env.Payload["action"])
		tunnelProtocol := tunnelProtocolFromPayload(env.Payload)
		previousTunnelProtocol := previousTunnelProtocolFromPayload(env.Payload, tunnelProtocol)
		if action == "" || action == "<nil>" {
			action = "unknown"
		}
		status := "applied"
		message := "Command applied."
		if err := s.applyControlWithProtocol(action, tunnelProtocol, previousTunnelProtocol); err != nil {
			status = "failed"
			message = err.Error()
			_ = s.publishEvent("control", fmt.Sprintf("Control command failed: %s: %v", action, err))
		} else {
			_ = s.publishEvent("control", fmt.Sprintf("Control command applied: %s", action))
		}
		_ = s.publish("control/ack", s.envelope("control/ack", env.RequestID, map[string]any{
			"status":  status,
			"action":  action,
			"message": message,
		}))
	case s.topic("config/push"):
		status := "applied"
		message := "Config applied."
		if err := s.applyConfigPush(env.Payload); err != nil {
			status = "failed"
			message = err.Error()
			_ = s.publishEvent("config_push", fmt.Sprintf("Config push failed: %v", err))
		} else {
			_ = s.publishEvent("config_push", "Config push applied.")
		}
		_ = s.publish("config/push/ack", s.envelope("config/push/ack", env.RequestID, map[string]any{
			"status":  status,
			"message": message,
		}))
	}
}

func (s *Session) publishHeartbeat() error {
	lock := s.lifecycleMu
	lock.Lock()
	defer lock.Unlock()
	wgOnline, err := s.tunnelStatus()
	if err != nil {
		// Keep the control channel available for repair, without reporting a false stopped state.
		return s.publishEvent("runtime_query_failed", fmt.Sprintf("Tunnel status query failed: %v", err))
	}
	return s.publish("heartbeat", s.envelope("heartbeat", "", map[string]any{
		"client_online": true,
		"wg_online":     wgOnline,
	}))
}

func (s *Session) publishEvent(event, message string) error {
	return s.publish("event", s.envelope("event", "", map[string]any{
		"level":   "info",
		"event":   event,
		"message": message,
	}))
}

func (s *Session) applyControl(action string) error {
	return s.applyControlWithProtocol(action, "wireguard", "wireguard")
}

func (s *Session) applyControlWithProtocol(action string, tunnelProtocol string, previousTunnelProtocol string) error {
	return s.controlConfiguration(action)
}

func (s *Session) applyConfigPush(payload map[string]any) error {
	if err := validateTunnelPayload(payload); err != nil {
		return err
	}
	return s.replaceConfiguration(payload)
}

func previousTunnelProtocolFromPayload(payload map[string]any, targetProtocol string) string {
	previousProtocol := normalizeTunnelProtocol(fmt.Sprint(payload["previous_tunnel_protocol"]))
	if previousProtocol == "" {
		return targetProtocol
	}
	return previousProtocol
}

func normalizeTunnelProtocol(value string) string {
	switch strings.TrimSpace(value) {
	case "wireguard":
		return "wireguard"
	case "amneziawg", "amneziawg_2":
		return "amneziawg_2"
	default:
		return ""
	}
}

func inspectWireGuard(interfaceName string, tunnelProtocol string) (bool, string) {
	output, err := runWGShowInterface(interfaceName, tunnelProtocol)
	if err != nil {
		return false, err.Error()
	}
	return strings.TrimSpace(output) != "", ""
}

func runWGShowInterface(interfaceName string, tunnelProtocol string) (string, error) {
	if strings.TrimSpace(interfaceName) == "" {
		return "", fmt.Errorf("interface_name is required")
	}
	actual, _, err := queryInterface(interfaceName, tunnelProtocol)
	if err != nil {
		return "", err
	}
	if actual == "" {
		return "", fmt.Errorf("interface %s is absent", interfaceName)
	}
	return toolOutput(tunnelProtocol, "show", actual)
}

func runWGShow(tunnelProtocol string) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, tunnelTool(tunnelProtocol))
	output, err := cmd.CombinedOutput()
	text := string(output)
	if ctx.Err() != nil {
		return text, ctx.Err()
	}
	if err != nil {
		return text, err
	}
	if strings.TrimSpace(text) == "" {
		return text, fmt.Errorf("%s returned no interfaces", tunnelTool(tunnelProtocol))
	}
	return text, nil
}

func startWireGuard(interfaceName string, configPath string, tunnelProtocol string) error {
	if _, err := os.Stat(configPath); err != nil {
		return err
	}
	if runtime.GOOS == "windows" {
		if err := runCommand(tunnelServiceTool(tunnelProtocol), "/installtunnelservice", configPath); err != nil {
			return err
		}
		return waitWireGuardStarted(interfaceName, configPath, tunnelProtocol, 15*time.Second)
	}
	return runCommand(tunnelQuickTool(tunnelProtocol), "up", configPath)
}

func stopWireGuard(interfaceName string, configPath string, tunnelProtocol string) error {
	if runtime.GOOS == "windows" {
		return runCommand(tunnelServiceTool(tunnelProtocol), "/uninstalltunnelservice", interfaceName)
	}
	return runCommand(tunnelQuickTool(tunnelProtocol), "down", configPath)
}

func waitWireGuardStarted(interfaceName string, configPath string, tunnelProtocol string, timeout time.Duration) error {
	deadline := time.Now().Add(timeout)
	var lastDetail string
	stableSince := time.Time{}
	for {
		running, detail := inspectWireGuard(interfaceName, tunnelProtocol)
		serviceRunning, serviceDetail := windowsTunnelServiceRunning(interfaceName, configPath, tunnelProtocol)
		if running && serviceRunning {
			if stableSince.IsZero() {
				stableSince = time.Now()
			}
			if time.Since(stableSince) >= 3*time.Second {
				return nil
			}
		} else {
			stableSince = time.Time{}
		}
		if running && !serviceRunning {
			lastDetail = serviceDetail
		} else {
			lastDetail = detail
		}
		if lastDetail == "" {
			lastDetail = "interface or tunnel service is not running"
		}
		if time.Now().After(deadline) {
			return fmt.Errorf("wireguard interface %s did not start before timeout: %s%s", interfaceName, lastDetail, windowsTunnelServiceDiagnostics(interfaceName, configPath, tunnelProtocol))
		}
		time.Sleep(500 * time.Millisecond)
	}
}

func windowsTunnelServiceRunning(interfaceName string, configPath string, tunnelProtocol string) (bool, string) {
	if runtime.GOOS != "windows" {
		return true, ""
	}
	var details []string
	for _, serviceName := range windowsTunnelServiceNames(interfaceName, configPath, tunnelProtocol) {
		output, err := exec.Command("sc.exe", "query", serviceName).CombinedOutput()
		text := strings.TrimSpace(string(output))
		if err != nil {
			if text != "" {
				details = append(details, fmt.Sprintf("%s query failed: %s", serviceName, text))
			}
			continue
		}
		state := strings.ToLower(parseWindowsServiceState(text))
		if state == "running" {
			return true, ""
		}
		if state != "" {
			details = append(details, fmt.Sprintf("%s state=%s", serviceName, state))
		}
	}
	if len(details) == 0 {
		return false, "tunnel service was not found"
	}
	return false, strings.Join(details, "; ")
}

func windowsTunnelServiceDiagnostics(interfaceName string, configPath string, tunnelProtocol string) string {
	if runtime.GOOS != "windows" {
		return ""
	}
	var sections []string
	for _, serviceName := range windowsTunnelServiceNames(interfaceName, configPath, tunnelProtocol) {
		output, err := exec.Command("sc.exe", "queryex", serviceName).CombinedOutput()
		text := strings.TrimSpace(string(output))
		if err == nil && text != "" {
			sections = append(sections, fmt.Sprintf("sc queryex %s output:\n%s", serviceName, text))
			continue
		}
		if text != "" {
			sections = append(sections, fmt.Sprintf("sc queryex %s failed: %v\n%s", serviceName, err, text))
		} else {
			sections = append(sections, fmt.Sprintf("sc queryex %s failed: %v", serviceName, err))
		}
	}
	if len(sections) == 0 {
		return ""
	}
	return "\n\n" + strings.Join(sections, "\n\n")
}

func windowsTunnelServiceNames(interfaceName string, configPath string, tunnelProtocol string) []string {
	interfaceName = strings.TrimSpace(interfaceName)
	names := make([]string, 0, 4)
	addName := func(prefix string, name string) {
		name = strings.TrimSpace(name)
		if name == "" {
			return
		}
		serviceName := prefix + name
		for _, existing := range names {
			if strings.EqualFold(existing, serviceName) {
				return
			}
		}
		names = append(names, serviceName)
	}
	if tunnelProtocol == "amneziawg_2" {
		addName("AmneziaWGTunnel$", interfaceName)
		addName("WireGuardTunnel$", interfaceName)
	} else {
		addName("WireGuardTunnel$", interfaceName)
	}
	configBase := strings.TrimSuffix(filepath.Base(configPath), filepath.Ext(configPath))
	if tunnelProtocol == "amneziawg_2" {
		addName("AmneziaWGTunnel$", configBase)
		addName("WireGuardTunnel$", configBase)
	} else {
		addName("WireGuardTunnel$", configBase)
	}
	return names
}

func parseWindowsServiceState(output string) string {
	matches := regexp.MustCompile(`STATE\s+:\s+\d+\s+([A-Z_]+)`).FindStringSubmatch(output)
	if len(matches) == 2 {
		return matches[1]
	}
	return ""
}

func runCommand(name string, args ...string) error {
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, name, args...)
	output, err := cmd.CombinedOutput()
	if ctx.Err() != nil {
		return ctx.Err()
	}
	if err != nil {
		text := strings.TrimSpace(string(output))
		if text != "" {
			return fmt.Errorf("%s %s failed: %w\n%s", name, strings.Join(args, " "), err, text)
		}
		return fmt.Errorf("%s %s failed: %w", name, strings.Join(args, " "), err)
	}
	return nil
}

func tunnelProtocolFromPayload(payload map[string]any) string {
	value := strings.TrimSpace(fmt.Sprint(payload["tunnel_protocol"]))
	if value == "amneziawg" || value == "amneziawg_2" {
		return "amneziawg_2"
	}
	return "wireguard"
}

func validateTunnelPayload(payload map[string]any) error {
	for _, key := range []string{"tunnel_protocol", "previous_tunnel_protocol"} {
		value := strings.TrimSpace(fmt.Sprint(payload[key]))
		if value != "" && value != "<nil>" && normalizeTunnelProtocol(value) == "" {
			return fmt.Errorf("unsupported %s: %s", key, value)
		}
	}
	version := strings.TrimSpace(fmt.Sprint(payload["awg_version"]))
	if version != "" && version != "<nil>" && version != "1.5" && version != "2.0" && version != "3.1" {
		return fmt.Errorf("unsupported AWG version: %s", version)
	}
	return nil
}

func tunnelTool(tunnelProtocol string) string {
	if tunnelProtocol == "amneziawg_2" {
		return "awg"
	}
	return "wg"
}

func tunnelQuickTool(tunnelProtocol string) string {
	if tunnelProtocol == "amneziawg_2" {
		return "awg-quick"
	}
	return "wg-quick"
}

func tunnelServiceTool(tunnelProtocol string) string {
	if tunnelProtocol == "amneziawg_2" {
		return "amneziawg.exe"
	}
	return "wireguard.exe"
}

func (s *Session) publish(kind string, env Envelope) error {
	body, err := json.Marshal(env)
	if err != nil {
		return err
	}
	ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
	defer cancel()
	_, err = s.client.Publish(ctx, &pahomqtt.Publish{
		Topic:   s.topic(kind),
		Payload: body,
		QoS:     1,
	})
	return err
}

func (s *Session) logf(format string, args ...any) {
	if s.logger == nil {
		return
	}
	fmt.Fprintf(s.logger, "%s %s\n", time.Now().Format(time.RFC3339), fmt.Sprintf(format, args...))
}

func (s *Session) envelope(kind, requestID string, payload map[string]any) Envelope {
	return Envelope{
		Type:      kind,
		RequestID: requestID,
		ConfigID:  s.configID,
		NodeID:    s.nodeID,
		BootID:    s.bootID,
		SessionID: s.sessionID,
		SentAt:    time.Now().UTC().Format(time.RFC3339),
		Payload:   payload,
	}
}

func (s *Session) topic(kind string) string {
	return fmt.Sprintf("wfm/%s/%s/%s", s.configID, s.nodeID, kind)
}
