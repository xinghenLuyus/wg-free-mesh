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
		fmt.Fprintln(stderr, "No profiles. Waiting for wfmctl bind.")
		<-ctx.Done()
		return nil
	}
	fmt.Fprintf(stderr, "Loaded %d profile(s).\n", len(profiles))

	var wg sync.WaitGroup
	for _, item := range profiles {
		p := item
		wg.Add(1)
		go func() {
			defer wg.Done()
			connectedOnce := false
			for {
				if ctx.Err() != nil {
					return
				}
				session := wfmmqtt.NewSession(p, stderr, connectedOnce)
				if err := session.Run(ctx); err != nil && ctx.Err() == nil {
					if session.Connected() {
						connectedOnce = true
					}
					time.Sleep(5 * time.Second)
				}
			}
		}()
	}
	wg.Wait()
	return nil
}
