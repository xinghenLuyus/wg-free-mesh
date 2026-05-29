# WG 环境安装

WG Free Mesh 客户端负责接收控制台下发的配置和控制命令。真正启动隧道时，机器上还需要准备对应的 WireGuard 或 AmneziaWG 工具链。

客户端安装时会检测当前主机是否已经具备 WG 工具链。缺少工具链时，客户端会给出提示；准备好工具链后，再回到控制台下发配置并启动隧道。

## WireGuard 工具链

如果只使用普通 WireGuard 配置，安装 WireGuard 即可。最简单的做法是直接按官方安装页选择自己的系统：

[WireGuard 安装页](https://www.wireguard.com/install/)

## AmneziaWG 工具链

如果配置使用 AmneziaWG 2.0，则需要安装 AmneziaWG 客户端或 `awg` 工具链。也可以先从 [Amnezia 官方文档入口](https://docs.amnezia.org/documentation/alternative-clients/) 选择对应平台。

常见平台入口：

- Android、iOS、macOS：在 Play 商店或 App Store 搜索 `AmneziaWG`。
- Windows：[AmneziaWG Windows Client](https://github.com/amnezia-vpn/amneziawg-windows-client/releases)。
- Linux、macOS：[AmneziaWG Tools](https://github.com/amnezia-vpn/amneziawg-tools)。

## 安装后检查

安装完成后，在终端里确认命令可用：

```bash
wg --version
awg --version
```

普通 WireGuard 环境只需要 `wg` 可用；AmneziaWG 环境需要 `awg` 可用。

如果某个命令不存在，回到对应官方页面重新安装或检查 PATH。工具链准备好以后，再回到 WG Free Mesh 控制台下发配置并启动隧道。
