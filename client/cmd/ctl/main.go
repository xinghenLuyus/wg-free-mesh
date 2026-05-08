package main

import (
	"flag"
	"fmt"
	"os"

	"wfm/client/internal/bind"
	"wfm/client/internal/profile"
	"wfm/client/internal/service"
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
	case "service":
		if len(os.Args) < 3 {
			serviceUsage()
			os.Exit(1)
		}
		if err := runServiceCommand(os.Args[2]); err != nil {
			fmt.Fprintf(os.Stderr, "service %s failed: %v\n", os.Args[2], err)
			os.Exit(1)
		}
	default:
		usage()
		os.Exit(1)
	}
}

func runServiceCommand(action string) error {
	switch action {
	case "install":
		return service.Install()
	case "uninstall":
		return service.Uninstall()
	case "start":
		return service.Start()
	case "stop":
		return service.Stop()
	case "restart":
		return service.Restart()
	case "status", "state":
		return service.Status()
	default:
		serviceUsage()
		return fmt.Errorf("unknown service action: %s", action)
	}
}

func usage() {
	fmt.Println("Usage:")
	fmt.Println("  wfmctl bind --server <url> --token <token>")
	fmt.Println("  wfmctl list")
	fmt.Println("  wfmctl service <install|uninstall|start|stop|restart|status>")
}

func serviceUsage() {
	fmt.Println("Usage:")
	fmt.Println("  wfmctl service install")
	fmt.Println("  wfmctl service uninstall")
	fmt.Println("  wfmctl service start")
	fmt.Println("  wfmctl service stop")
	fmt.Println("  wfmctl service restart")
	fmt.Println("  wfmctl service status")
	fmt.Println("  wfmctl service state")
}
