package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	wfmmqtt "wfm/client/internal/mqtt"
	"wfm/client/internal/profile"
)

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	profiles, err := profile.LoadAll()
	if err != nil {
		fmt.Fprintf(os.Stderr, "load profiles failed: %v\n", err)
		os.Exit(1)
	}
	if len(profiles) == 0 {
		fmt.Println("No profiles. Run wfmctl bind first.")
		return
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
					fmt.Fprintf(os.Stderr, "mqtt session failed profile=%s err=%v\n", p.Profile.ProfileID, err)
					time.Sleep(5 * time.Second)
				}
			}
		}()
	}
	wg.Wait()
}

