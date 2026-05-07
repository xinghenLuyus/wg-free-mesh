package mqtt

import (
	"context"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"net"
	"os/exec"
	"runtime"
	"strconv"
	"strings"
	"time"

	pahomqtt "github.com/eclipse/paho.golang/paho"

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
	profile   profile.Profile
	bootID    string
	sessionID string
	client    *pahomqtt.Client
}

func NewSession(p profile.Profile) *Session {
	now := time.Now().UnixNano()
	return &Session{
		profile:   p,
		bootID:    fmt.Sprintf("boot-%d", now),
		sessionID: fmt.Sprintf("session-%d", now),
	}
}

func (s *Session) Run(ctx context.Context) error {
	conn, err := s.dial()
	if err != nil {
		return err
	}
	defer conn.Close()
	will, _ := json.Marshal(s.envelope("event", "", map[string]any{
		"level":   "info",
		"event":   "offline",
		"message": "Client disconnected with will message.",
	}))
	client := pahomqtt.NewClient(pahomqtt.ClientConfig{
		Conn: conn,
		Router: pahomqtt.NewSingleHandlerRouter(func(m *pahomqtt.Publish) {
			s.handleMessage(m)
		}),
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
	if err := s.subscribe(ctx); err != nil {
		return err
	}
	_ = s.publishEvent("online", "Client connected and MQTT session established.")
	_ = s.publishHeartbeat()
	ticker := time.NewTicker(30 * time.Minute)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return nil
		case <-ticker.C:
			_ = s.publishHeartbeat()
		}
	}
}

func (s *Session) dial() (net.Conn, error) {
	addr := net.JoinHostPort(s.profile.MQTT.Host, strconv.Itoa(s.profile.MQTT.Port))
	if s.profile.MQTT.TLS {
		return tls.Dial("tcp", addr, &tls.Config{MinVersion: tls.VersionTLS12, InsecureSkipVerify: true})
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
	var env Envelope
	_ = json.Unmarshal(m.Payload, &env)
	switch m.Topic {
	case s.topic("detect"):
		wgOnline, _ := inspectWireGuard()
		_ = s.publishEvent("detect", "Server detect command received.")
		_ = s.publish("detect/ack", s.envelope("detect/ack", env.RequestID, map[string]any{
			"status":        "applied",
			"client_online": true,
			"wg_online":     wgOnline,
			"platform":      runtime.GOOS,
			"message":       "Detect completed.",
		}))
	case s.topic("info"):
		action := fmt.Sprint(env.Payload["action"])
		if action == "" || action == "<nil>" {
			action = "wg_show"
		}
		output, err := runWGShow()
		level := "info"
		message := "wg show completed."
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
		if action == "" || action == "<nil>" {
			action = "unknown"
		}
		_ = s.publishEvent("control", fmt.Sprintf("Received control command: %s", action))
		_ = s.publish("control/ack", s.envelope("control/ack", env.RequestID, map[string]any{
			"status":  "applied",
			"action":  action,
			"message": "Command acknowledged by minimal Go client.",
		}))
	case s.topic("config/push"):
		_ = s.publishEvent("config_push", "Received config push command.")
		_ = s.publish("config/push/ack", s.envelope("config/push/ack", env.RequestID, map[string]any{
			"status":  "accepted",
			"message": "Config received by minimal Go client.",
		}))
	}
}

func (s *Session) publishHeartbeat() error {
	wgOnline, _ := inspectWireGuard()
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

func inspectWireGuard() (bool, string) {
	output, err := runWGShow()
	if err != nil {
		return false, err.Error()
	}
	return strings.TrimSpace(output) != "", ""
}

func runWGShow() (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, "wg", "show")
	output, err := cmd.CombinedOutput()
	text := string(output)
	if ctx.Err() != nil {
		return text, ctx.Err()
	}
	if err != nil {
		return text, err
	}
	if strings.TrimSpace(text) == "" {
		return text, fmt.Errorf("wg show returned no interfaces")
	}
	return text, nil
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

func (s *Session) envelope(kind, requestID string, payload map[string]any) Envelope {
	return Envelope{
		Type:      kind,
		RequestID: requestID,
		ConfigID:  s.profile.Profile.ConfigID,
		NodeID:    s.profile.Profile.NodeID,
		BootID:    s.bootID,
		SessionID: s.sessionID,
		SentAt:    time.Now().UTC().Format(time.RFC3339),
		Payload:   payload,
	}
}

func (s *Session) topic(kind string) string {
	return fmt.Sprintf("wfm/%s/%s/%s", s.profile.Profile.ConfigID, s.profile.Profile.NodeID, kind)
}
