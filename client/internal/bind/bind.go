package bind

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"runtime"
	"strings"
	"time"

	"wfm/client/internal/profile"
)

const Version = "0.1.0"

type requestBody struct {
	Token         string `json:"token"`
	Hostname      string `json:"hostname"`
	Platform      string `json:"platform"`
	ClientVersion string `json:"client_version"`
}

type apiResponse struct {
	Success bool `json:"success"`
	Data    struct {
		Profile    profile.ProfileMeta `json:"profile"`
		MQTT       profile.MQTTConfig  `json:"mqtt"`
		DesiredConf string             `json:"desired_conf"`
	} `json:"data"`
	Error struct {
		Message string `json:"message"`
	} `json:"error"`
}

func Run(serverURL, token string) (profile.Profile, error) {
	hostname, _ := os.Hostname()
	payload := requestBody{
		Token:         token,
		Hostname:      hostname,
		Platform:      runtime.GOOS,
		ClientVersion: Version,
	}
	body, err := json.Marshal(payload)
	if err != nil {
		return profile.Profile{}, err
	}
	target := strings.TrimRight(serverURL, "/") + "/api/client/v1/bind"
	client := http.Client{Timeout: 15 * time.Second}
	response, err := client.Post(target, "application/json", bytes.NewReader(body))
	if err != nil {
		return profile.Profile{}, err
	}
	defer response.Body.Close()
	var decoded apiResponse
	if err := json.NewDecoder(response.Body).Decode(&decoded); err != nil {
		return profile.Profile{}, err
	}
	if response.StatusCode >= 400 || !decoded.Success {
		if decoded.Error.Message != "" {
			return profile.Profile{}, fmt.Errorf(decoded.Error.Message)
		}
		return profile.Profile{}, fmt.Errorf("bind failed: HTTP %d", response.StatusCode)
	}
	decoded.Data.Profile.ServerURL = strings.TrimRight(serverURL, "/")
	result := profile.Profile{Profile: decoded.Data.Profile, MQTT: decoded.Data.MQTT}
	if err := profile.Save(result, decoded.Data.DesiredConf); err != nil {
		return profile.Profile{}, err
	}
	return result, nil
}

