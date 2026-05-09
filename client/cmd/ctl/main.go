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
	if len(os.Args) < 2 || isHelpArg(os.Args[1]) {
		rootHelp()
		return
	}
	if isVersionArg(os.Args[1]) {
		printVersion()
		return
	}

	cmd := os.Args[1]
	args := os.Args[2:]
	var err error
	switch cmd {
	case "help":
		if len(args) > 0 && isHelpArg(args[0]) {
			helpHelp()
			return
		}
		help(args)
	case "install":
		if hasHelp(args) {
			installHelp()
			return
		}
		if err = noArgs("install", args); err != nil {
			break
		}
		err = service.Install()
	case "uninstall":
		err = runUninstall(args)
	case "bind":
		err = runBind(args)
	case "unbind":
		err = runUnbind(args)
	case "list":
		if hasHelp(args) {
			listHelp()
			return
		}
		if err = noArgs("list", args); err != nil {
			break
		}
		err = runList()
	case "status":
		if hasHelp(args) {
			statusHelp()
			return
		}
		if err = noArgs("status", args); err != nil {
			break
		}
		err = service.Status()
	case "logs":
		err = runLogs(args)
	case "start":
		if hasHelp(args) {
			startHelp()
			return
		}
		if err = noArgs("start", args); err != nil {
			break
		}
		err = service.Start()
	case "stop":
		if hasHelp(args) {
			stopHelp()
			return
		}
		if err = noArgs("stop", args); err != nil {
			break
		}
		err = service.Stop()
	case "restart":
		if hasHelp(args) {
			restartHelp()
			return
		}
		if err = noArgs("restart", args); err != nil {
			break
		}
		err = service.Restart()
	case "version":
		if hasHelp(args) {
			versionHelp()
			return
		}
		if err = noArgs("version", args); err != nil {
			break
		}
		printVersion()
	case "service":
		err = fmt.Errorf("the service subcommand has been removed; use: wfmctl install | uninstall | start | stop | restart | status | logs")
	default:
		rootHelp()
		err = fmt.Errorf("unknown command: %s", cmd)
	}
	if err != nil {
		fmt.Fprintf(os.Stderr, "%v\n", err)
		os.Exit(1)
	}
}

func runUninstall(args []string) error {
	if hasHelp(args) {
		uninstallHelp()
		return nil
	}
	fs := flag.NewFlagSet("uninstall", flag.ContinueOnError)
	fs.SetOutput(os.Stderr)
	purge := fs.Bool("purge", false, "delete local profiles, runtime data, and logs")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if fs.NArg() != 0 {
		return fmt.Errorf("usage: wfmctl uninstall [--purge]")
	}
	if err := service.Uninstall(); err != nil {
		return err
	}
	if *purge {
		if err := service.PurgeData(); err != nil {
			return err
		}
		fmt.Println("Local profiles, runtime data, and logs removed.")
	}
	return nil
}

func runBind(args []string) error {
	if hasHelp(args) {
		bindHelp()
		return nil
	}
	bindCmd := flag.NewFlagSet("bind", flag.ContinueOnError)
	bindCmd.SetOutput(os.Stderr)
	server := bindCmd.String("server", "", "wfm server URL")
	token := bindCmd.String("token", "", "one-time bind token")
	if err := bindCmd.Parse(args); err != nil {
		return err
	}
	rest := bindCmd.Args()
	if *server == "" && len(rest) >= 1 {
		*server = rest[0]
	}
	if *token == "" && len(rest) >= 2 {
		*token = rest[1]
	}
	if len(rest) > 2 {
		return fmt.Errorf("usage: wfmctl bind --server <url> --token <token>")
	}
	if *server == "" || *token == "" {
		return fmt.Errorf("server and token are required")
	}
	p, err := bind.Run(*server, *token)
	if err != nil {
		return fmt.Errorf("bind failed: %w", err)
	}
	fmt.Printf("Bound profile %s for node %s\n", p.Profile.ProfileID, p.Profile.NodeName)
	return restartIfRunning()
}

func runUnbind(args []string) error {
	if hasHelp(args) {
		unbindHelp()
		return nil
	}
	unbindCmd := flag.NewFlagSet("unbind", flag.ContinueOnError)
	unbindCmd.SetOutput(os.Stderr)
	all := unbindCmd.Bool("all", false, "remove all local bindings")
	if err := unbindCmd.Parse(args); err != nil {
		return err
	}
	removed := 0
	if *all {
		if unbindCmd.NArg() != 0 {
			return fmt.Errorf("usage: wfmctl unbind --all")
		}
		count, err := profile.RemoveAll()
		if err != nil {
			return err
		}
		removed = count
		fmt.Printf("Removed %d local bindings.\n", removed)
	} else {
		rest := unbindCmd.Args()
		if len(rest) != 1 {
			return fmt.Errorf("usage: wfmctl unbind <profile_id> or wfmctl unbind --all")
		}
		if err := profile.Remove(rest[0]); err != nil {
			return err
		}
		removed = 1
		fmt.Printf("Removed local binding %s.\n", rest[0])
	}
	if removed > 0 {
		return restartIfRunning()
	}
	return nil
}

func runList() error {
	items, _, err := profile.Summaries()
	if err != nil {
		return fmt.Errorf("list failed: %w", err)
	}
	if len(items) == 0 {
		fmt.Println("No profiles.")
		return nil
	}
	for _, item := range items {
		fmt.Printf("%s | %s/%s | server=%s profile=%s desired=%s mqtt=%s:%d tls=%t\n",
			item.ProfileID,
			item.ConfigName,
			item.NodeName,
			item.ServerURL,
			statusLabel(item.ProfilePresent, item.ProfileValid),
			statusLabel(item.DesiredPresent, true),
			item.MQTTHost,
			item.MQTTPort,
			item.MQTTTLS,
		)
	}
	return nil
}

func runLogs(args []string) error {
	if hasHelp(args) {
		logsHelp()
		return nil
	}
	logsCmd := flag.NewFlagSet("logs", flag.ContinueOnError)
	logsCmd.SetOutput(os.Stderr)
	lines := logsCmd.Int("lines", 100, "number of log lines")
	if err := logsCmd.Parse(args); err != nil {
		return err
	}
	if logsCmd.NArg() != 0 {
		return fmt.Errorf("usage: wfmctl logs [--lines <n>]")
	}
	return service.Logs(*lines)
}

func noArgs(command string, args []string) error {
	if len(args) == 0 {
		return nil
	}
	return fmt.Errorf("usage: wfmctl %s", command)
}

func restartIfRunning() error {
	running, err := service.IsRunning()
	if err == nil && running {
		fmt.Println("Restarting service to apply changes.")
		return service.Restart()
	}
	return nil
}

func help(args []string) {
	if len(args) == 0 {
		rootHelp()
		return
	}
	switch args[0] {
	case "install":
		installHelp()
	case "uninstall":
		uninstallHelp()
	case "bind":
		bindHelp()
	case "unbind":
		unbindHelp()
	case "list":
		listHelp()
	case "status":
		statusHelp()
	case "logs":
		logsHelp()
	case "start":
		startHelp()
	case "stop":
		stopHelp()
	case "restart":
		restartHelp()
	case "version":
		versionHelp()
	case "help":
		helpHelp()
	default:
		rootHelp()
	}
}

func hasHelp(args []string) bool {
	for _, arg := range args {
		if isHelpArg(arg) {
			return true
		}
	}
	return false
}

func isHelpArg(arg string) bool {
	return arg == "-h" || arg == "--help"
}

func isVersionArg(arg string) bool {
	return arg == "-v" || arg == "--version"
}

func printVersion() {
	fmt.Printf("wfmctl %s\n", bind.Version)
}

func statusLabel(present bool, valid bool) string {
	if !present {
		return "missing"
	}
	if !valid {
		return "invalid"
	}
	return "present"
}

func rootHelp() {
	fmt.Println(`WG Free Mesh client

Usage:
  wfmctl <command> [options]

Commands:
  install      Install service, enable autostart, start service, add wfmctl to PATH
  uninstall    Remove service and PATH entry; keep local data unless --purge is used
  bind         Add a local binding with a one-time token
  unbind       Remove local binding files; restarts service if running
  list         List local bindings
  status       Show service state and local binding health
  logs         Show service logs
  start        Start installed service
  stop         Stop service; autostart remains enabled
  restart      Restart service and reload local bindings
  version      Show version
  help         Show command help

Options:
  -h, --help     Show help
  -v, --version  Show version

Use "wfmctl help <command>" for details.`)
}

func installHelp() {
	fmt.Println(`Install service

Usage:
  wfmctl install

Effects:
  - creates/updates system service
  - enables autostart
  - starts service
  - adds current wfmctl directory to global PATH
  - creates local data directories

Requires administrator/root privileges.`)
}

func uninstallHelp() {
	fmt.Println(`Uninstall service

Usage:
  wfmctl uninstall [--purge]

Options:
  --purge    also delete local profiles, runtime data, and logs

Default effects:
  - stops service
  - disables autostart
  - removes service definition
  - removes PATH entry
  - keeps local profiles, runtime data, and logs

With --purge:
  - also deletes all local WG Free Mesh data on this machine
  - does not revoke server-side node permissions

Requires administrator/root privileges.`)
}

func bindHelp() {
	fmt.Println(`Bind this machine

Usage:
  wfmctl bind --server <url> --token <token>
  wfmctl bind <url> <token>

Options:
  --server    Server URL
  --token     One-time bind token

Effects:
  - writes local profile and credentials
  - restarts service if running

Requires administrator/root privileges.`)
}

func unbindHelp() {
	fmt.Println(`Remove local binding

Usage:
  wfmctl unbind <profile_id>
  wfmctl unbind --all

Options:
  --all    remove all local bindings

Effects:
  - deletes local binding files
  - restarts service if running
  - does not revoke server-side node permissions`)
}

func listHelp() {
	fmt.Println(`List local bindings

Usage:
  wfmctl list

Shows:
  - profile id
  - config/node name
  - server URL
  - MQTT endpoint
  - local file status`)
}

func statusHelp() {
	fmt.Println(`Show local status

Usage:
  wfmctl status

Shows:
  - installed/running/autostart state
  - service binary path
  - profile root
  - binding count
  - local file status`)
}

func logsHelp() {
	fmt.Println(`Show service logs

Usage:
  wfmctl logs [--lines <n>]

Options:
  --lines <n>    log lines to show, default 100`)
}

func startHelp() {
	fmt.Println(`Start service

Usage:
  wfmctl start

Starts the installed service.
Requires administrator/root privileges.`)
}

func stopHelp() {
	fmt.Println(`Stop service

Usage:
  wfmctl stop

Stops the running service.
Autostart remains enabled.
Requires administrator/root privileges.`)
}

func restartHelp() {
	fmt.Println(`Restart service

Usage:
  wfmctl restart

Restarts the service and reloads local bindings.
Requires administrator/root privileges.`)
}

func versionHelp() {
	fmt.Println(`Show version

Usage:
  wfmctl version
  wfmctl --version
  wfmctl -v`)
}

func helpHelp() {
	fmt.Println(`Show help

Usage:
  wfmctl help [command]
  wfmctl <command> -h
  wfmctl <command> --help`)
}
