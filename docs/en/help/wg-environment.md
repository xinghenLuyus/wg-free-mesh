# WG Environment Install

The WG Free Mesh client receives configs and control commands from the console. To actually start a tunnel, the machine also needs the matching WireGuard or AmneziaWG toolchain.

During installation, the client checks whether the current host already has the WG toolchain. If a toolchain is missing, the client shows a hint. After the toolchain is ready, return to the console to push config and start the tunnel.

## WireGuard Toolchain

If the config uses standard WireGuard, install WireGuard. The simplest path is to open the official install page and choose your operating system:

[WireGuard Install](https://www.wireguard.com/install/)

## AmneziaWG Toolchain

If the config uses AmneziaWG 2.0, install the AmneziaWG client or the `awg` toolchain. You can also start from the [Amnezia official documentation](https://docs.amnezia.org/documentation/alternative-clients/) and choose the matching platform.

Common platform links:

- Android, iOS, macOS: search for `AmneziaWG` in Play Store or App Store.
- Windows: [AmneziaWG Windows Client](https://github.com/amnezia-vpn/amneziawg-windows-client/releases).
- Linux, macOS: [AmneziaWG Tools](https://github.com/amnezia-vpn/amneziawg-tools).

## Check After Installation

After installation, confirm the commands are available in a terminal:

```bash
wg --version
awg --version
```

Standard WireGuard only needs `wg`; AmneziaWG needs `awg`.

If a command is missing, reinstall from the corresponding official page or check PATH. After the toolchain is ready, return to the WG Free Mesh console to push config and start the tunnel.
