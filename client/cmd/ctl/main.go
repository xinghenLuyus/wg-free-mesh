package main

import (
	"flag"
	"fmt"
	"os"

	"wfm/client/internal/bind"
	"wfm/client/internal/profile"
)

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(1)
	}
	switch os.Args[1] {
	case "bind":
		bindCmd := flag.NewFlagSet("bind", flag.ExitOnError)
		server := bindCmd.String("server", "", "wfm server URL")
		token := bindCmd.String("token", "", "one-time bind token")
		_ = bindCmd.Parse(os.Args[2:])
		if *server == "" || *token == "" {
			fmt.Fprintln(os.Stderr, "server and token are required")
			os.Exit(1)
		}
		p, err := bind.Run(*server, *token)
		if err != nil {
			fmt.Fprintf(os.Stderr, "bind failed: %v\n", err)
			os.Exit(1)
		}
		fmt.Printf("Bound profile %s for node %s\n", p.Profile.ProfileID, p.Profile.NodeName)
	case "list":
		items, err := profile.LoadAll()
		if err != nil {
			fmt.Fprintf(os.Stderr, "list failed: %v\n", err)
			os.Exit(1)
		}
		if len(items) == 0 {
			fmt.Println("No profiles.")
			return
		}
		for _, item := range items {
			fmt.Printf("%s | %s/%s | mqtt=%s:%d\n", item.Profile.ProfileID, item.Profile.ConfigName, item.Profile.NodeName, item.MQTT.Host, item.MQTT.Port)
		}
	default:
		usage()
		os.Exit(1)
	}
}

func usage() {
	fmt.Println("Usage:")
	fmt.Println("  wfmctl bind --server <url> --token <token>")
	fmt.Println("  wfmctl list")
}

