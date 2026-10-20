# Client and Control

The client connects a machine to WG Free Mesh and receives config and control commands from the console.

The client is command-line only. There is no local GUI. This makes it a better fit for servers, edge devices, and operational automation; installation, binding, status checks, logs, and service operations can all be scripted.

The client maps server names to local interface names: combined names up to 15 characters are kept; longer names use the first 12 characters of the encoded config name from binding. Mappings are stored locally without changing console names or download filenames. A name already used by another local binding produces an error.

## Download the Client

Open the download page from the tool list and choose client download. The page supports two sources:

- GitHub release: looks for a Release package matching the current server version, then lets the browser download directly from GitHub.
- Local source build: asks the server to build a client package from the local `client/` source tree. This is mainly for development and temporary verification.

If GitHub release is selected and the current version or target package does not exist, the page shows an error immediately.

Packages are separated by operating system and architecture. Windows supports the common 64-bit build and an additional 32-bit build. After extraction, keep the client in a stable directory. If the directory is moved, run install again.

## Update the Client

Use `sudo` on Linux/macOS and an administrator terminal on Windows (without `sudo`):

```bash
sudo wfmctl update             # GitHub release matching the server
sudo wfmctl update --server    # Build and download from the server
sudo wfmctl update --server 2  # Select the server of binding number 2
```

Select a binding by its number in `wfmctl list` or full Profile ID; omission selects number 1. Numbers follow a fixed local binding-directory name order. The default GitHub source also supports `wfmctl update 2`. Selection determines the version and download source, but updates the entire local client installation.

Both programs may only upgrade to the selected server version. Equal versions do not reinstall; downgrades are rejected. Stable and `rc.n` versions are supported. The server must expose the client update API. GitHub packages require an accompanying `.zip.sha256` file and an internal `package.json`. HTTP is permitted only on loopback; other addresses require HTTPS. Sources never switch automatically.

After download and verification, a separate helper waits for the original command and service process to exit, replaces the two programs actually used by the service, and restores the original service and managed tunnel running states. Handoff is not success: inspect the printed `result.log`; `state.json` records progress and results. Windows, macOS launchd, and Linux systemd use their respective service managers. OpenRC is not supported by this update flow.

Updates do not reinstall the service or change bindings, autostart settings, or tunnel parameters. Userspace tunnels may briefly disconnect. Failed replacement attempts restore original programs only before activation; activation is never followed by an automatic downgrade. Interrupted transactions, unconfirmed process exit, or ambiguous interface ownership preserve the evidence and stop automatic processing. Resolve unfinished configuration replacement or historical tunnel errors and exit manually running agent instances before updating. The next update preserves the previous terminal record in `update/last-result.json`.

## Install

Installation requires administrator or root privileges. After installation, `wfmctl` is added to PATH, so most daily commands use the same syntax on all three platforms.

On Windows, use an elevated PowerShell from the client directory:

```powershell
.\wfmctl.exe install; $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine")
```

On Linux and macOS, run from the client directory:

```bash
chmod +x ./wfmctl ./wfm-agent && sudo ./wfmctl install
```

During install, the client prints its identity and version, then checks whether `wg` and `awg` are available. Missing toolchains should produce a clear hint but should not block installation.

## CLI Commands

After installation, daily commands use `wfmctl` directly. Reinstalling from the extracted directory is the main exception.

| Command | Purpose | Notes |
| --- | --- | --- |
| `wfmctl install` | Install the service. | Requires administrator or root privileges. Prefer the platform-specific install command above for first install. |
| `wfmctl uninstall` | Uninstall the service. | Stops the service, disables autostart, removes the service definition and PATH entry, and keeps local data. |
| `wfmctl uninstall --purge` | Uninstall and remove local data. | Also deletes local profiles, runtime data, and logs. |
| `wfmctl bind --server <url> --token <token>` | Bind a node. | Copy the bind command from the node control page. |
| `wfmctl bind <url> <token>` | Short bind form. | Equivalent to passing `--server` and `--token`. |
| `wfmctl unbind <profile_id>` | Remove one local binding. | Does not revoke server-side node permissions. |
| `wfmctl unbind --all` | Remove all local bindings. | Useful when cleaning up multiple profiles. |
| `wfmctl list` | List local bindings. | Shows profile, config/node name, server URL, and MQTT information. |
| `wfmctl status` | Show service and binding status. | Run this first when troubleshooting. |
| `wfmctl logs` | Show service logs. | Defaults to the latest 100 lines. |
| `wfmctl logs --lines <n>` | Show a specific number of log lines. | Example: `wfmctl logs --lines 300`. |
| `wfmctl start` | Start the service. | Autostart configuration is not changed. |
| `wfmctl stop` | Stop the service. | Autostart remains enabled. |
| `wfmctl restart` | Restart the service. | Reloads local bindings and config. |
| `wfmctl version` | Show client version. | `wfmctl --version` and `wfmctl -v` also work. |
| `wfmctl help` | Show help. | Use `wfmctl help <command>` for subcommand help. |

On macOS, restarting a loaded service preserves its launchd registration; an unloaded service is registered again. Stop and reinstall wait for unloading, and failures report the original system error. If binding succeeds but service reload fails, keep the binding, resolve the service issue, and run `sudo wfmctl start`.

## First-Time Flow

Before binding, the client checks administrator/root privileges, agent service installation, and whether the profile directory can be created and written to. If a check fails, it stops locally without sending a bind request or consuming the one-time token.

Recommended order:

1. Create a config and node in the console.
2. Download the client for the target operating system and architecture.
3. Extract the client to a stable directory.
4. Run the install command.
5. Copy the bind command from the node control page.
6. Run the bind command.
7. Run `wfmctl status` and confirm the service is running.
8. Return to the console, push config, and start the tunnel.

## Check After Binding

After binding succeeds, check local status:

```bash
wfmctl status
```

Focus on:

- Whether `State` is `running`.
- Whether `Profiles` is greater than 0.
- Whether the binding shows the expected config and node name.
- Whether MQTT host, port, and TLS state match the deployment.

If `Profiles` is 0, this machine has no valid local binding. Copy a fresh bind command from the node control page.

## Troubleshooting with Logs

Client logs help diagnose service startup, MQTT connection, config push, and control command issues.

```bash
wfmctl logs --lines 300
```

The client records important state changes:

- Service start and stop.
- Profile loading.
- MQTT connected.
- MQTT disconnected.
- MQTT reconnected.
- Config push failure.
- Control command result.

Connection checks and retry attempts are not logged continuously, to avoid noisy logs.

## Node Control

The node control page depends on the client being online and MQTT being enabled. Common actions include:

- Refresh status.
- Push config.
- Start tunnel.
- Stop tunnel.
- View WireGuard / AmneziaWG state.
- Reset client binding.

When a client is reset, the system also deletes or disables the corresponding EMQX user and tries to disconnect the MQTT session immediately. The client must bind again before it can be controlled.

## When MQTT Is Disabled

If MQTT is disabled at the deployment level, client binding, endpoint control, online state, and remote commands are disabled system-wide. You can still maintain configs and static mesh data, but the console cannot drive client behavior.
