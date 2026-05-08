package agent

import (
	"context"
	"fmt"
	"io"
	"sync"
	"time"

	wfmmqtt "wfm/client/internal/mqtt"
	"wfm/client/internal/profile"
)

func Run(ctx context.Context, stderr io.Writer) error {
	profiles, err := profile.LoadAll()
	if err != nil {
		return fmt.Errorf("load profiles failed: %w", err)
	}
	if len(profiles) == 0 {
		fmt.Fprintln(stderr, "No profiles. Run wfmctl bind first.")
		return nil
	}

	var wg sync.WaitGroup
	for _, item := range profiles {
		p := item
		wg.Add(1)
		go func() {
			defer wg.Done()
			for {
				if ctx.Err() != nil {
					return
				}
				session := wfmmqtt.NewSession(p)
				if err := session.Run(ctx); err != nil && ctx.Err() == nil {
					fmt.Fprintf(stderr, "mqtt session failed profile=%s err=%v\n", p.Profile.ProfileID, err)
					time.Sleep(5 * time.Second)
				}
			}
		}()
	}
	wg.Wait()
	return nil
}
