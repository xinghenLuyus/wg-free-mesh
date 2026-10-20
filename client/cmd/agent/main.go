package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"syscall"

	"wfm/client/internal/agent"
	"wfm/client/internal/bind"
	"wfm/client/internal/service"
)

func main() {
	if len(os.Args) == 2 && (os.Args[1] == "version" || os.Args[1] == "--version" || os.Args[1] == "-v") {
		fmt.Printf("wfm-agent %s\n", bind.Version)
		return
	}
	if len(os.Args) > 1 && os.Args[1] == "service-run" {
		if err := service.RunAgentService(agent.Run); err != nil {
			fmt.Fprintf(os.Stderr, "service failed: %v\n", err)
			os.Exit(1)
		}
		return
	}

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	if err := agent.Run(ctx, os.Stderr); err != nil {
		fmt.Fprintf(os.Stderr, "%v\n", err)
		os.Exit(1)
	}
}
