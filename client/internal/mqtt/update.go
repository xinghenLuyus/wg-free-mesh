package mqtt

import (
	"errors"
	"fmt"
	"os"
	"wfm/client/internal/profile"
)

// UpdateTunnel contains identity only, never binding credentials or private keys.
type UpdateTunnel struct {
	ProfileID string `json:"profile_id"`
	Name      string `json:"name"`
	Protocol  string `json:"protocol"`
	PublicKey string `json:"public_key"`
	SHA256    string `json:"sha256"`
}

func CaptureUpdateTunnels() ([]UpdateTunnel, error) {
	profiles, err := profile.LoadAll()
	if err != nil {
		return nil, err
	}
	var result []UpdateTunnel
	for _, p := range profiles {
		dir, err := profile.Directory(p)
		if err != nil {
			return nil, err
		}
		pending, err := readTransition(dir)
		if err != nil {
			return nil, err
		}
		if pending != nil {
			return nil, fmt.Errorf("profile %s has an unfinished configuration replacement; resolve it before updating", p.Profile.ProfileID)
		}
		running, err := ownedRunning(p)
		if err != nil {
			return nil, err
		}
		if len(running) > 1 {
			return nil, fmt.Errorf("profile %s has multiple running tunnels; resolve leftovers before updating", p.Profile.ProfileID)
		}
		for _, b := range running {
			m := b.Manifest
			current, currentErr := currentBundle(p)
			if currentErr != nil && !os.IsNotExist(currentErr) {
				return nil, currentErr
			}
			if (currentErr == nil && (current.Manifest.SHA256 != m.SHA256 || current.Manifest.InterfaceName != m.InterfaceName || current.Manifest.Protocol != m.Protocol)) || (currentErr != nil && m.InterfaceName != profile.InterfaceName(p)) {
				return nil, fmt.Errorf("profile %s has a historical running tunnel; reconcile it before updating", p.Profile.ProfileID)
			}
			result = append(result, UpdateTunnel{p.Profile.ProfileID, m.InterfaceName, m.Protocol, m.PublicKey, m.SHA256})
		}
	}
	return result, nil
}

func RestoreUpdateTunnels(items []UpdateTunnel) error {
	var failures []error
	for _, item := range items {
		if err := restoreUpdateTunnel(item); err != nil {
			failures = append(failures, fmt.Errorf("profile %s: %w", item.ProfileID, err))
		}
	}
	return errors.Join(failures...)
}

func restoreUpdateTunnel(item UpdateTunnel) error {
	p, err := profile.Load(item.ProfileID)
	if err != nil {
		return err
	}
	all, err := candidates(p)
	if err != nil {
		return err
	}
	var target *profile.Bundle
	for i := range all {
		m := all[i].Manifest
		if m.InterfaceName == item.Name && m.Protocol == item.Protocol && m.PublicKey == item.PublicKey && m.SHA256 == item.SHA256 {
			target = &all[i]
			break
		}
	}
	if target == nil {
		return fmt.Errorf("profile %s changed during update; refusing to restore a stale tunnel", item.ProfileID)
	}
	// A concurrent configuration push can leave the old generation in history. Do not revive it.
	current, err := currentBundle(p)
	if err != nil && !os.IsNotExist(err) {
		return err
	}
	if err == nil && (current.Manifest.SHA256 != item.SHA256 || current.Manifest.InterfaceName != item.Name || current.Manifest.Protocol != item.Protocol) {
		return fmt.Errorf("profile %s current configuration changed during update", item.ProfileID)
	}
	running, err := ownedRunning(p)
	if err != nil {
		return err
	}
	if len(running) > 0 {
		if len(running) != 1 || running[0].Manifest.SHA256 != item.SHA256 || running[0].Manifest.InterfaceName != item.Name || running[0].Manifest.Protocol != item.Protocol {
			return fmt.Errorf("profile %s runtime changed during update", item.ProfileID)
		}
		return nil
	}
	if err = startBundle(*target); err != nil {
		return fmt.Errorf("restore profile %s: %w", item.ProfileID, err)
	}
	return nil
}
