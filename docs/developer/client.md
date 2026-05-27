# 客户端

客户端位于 `client/`，使用 Go 实现，由两个入口组成：

- `wfm-agent`：系统服务，长期运行。
- `wfmctl`：命令行工具，负责安装、绑定、状态、日志和服务控制。

客户端文档只解释实现边界。用户如何下载、安装和使用命令行，见 [客户端与控制](/usage/client)。

## 目录入口

| 目录 | 作用 |
| --- | --- |
| `client/cmd/agent` | agent 入口。 |
| `client/cmd/ctl` | wfmctl 入口。 |
| `client/internal` | 绑定、服务管理、MQTT、WireGuard/AmneziaWG 操作等内部实现。 |
| `client/build_release.py` | 发布构建脚本。 |

## 运行模型

`wfmctl install` 安装系统服务，并把当前客户端目录加入 PATH。服务启动后，`wfm-agent` 读取本地 profile，连接 MQTT，等待后端下发配置和控制命令。

常见本地状态：

- profile：服务端绑定返回的节点身份、服务端地址、MQTT 参数。
- desired config：后端期望客户端应用的配置。
- applied config：客户端已经应用过的配置。
- runtime/logs：服务运行日志和本地运行信息。

## 绑定流程

1. 控制台为端点生成一次性绑定命令。
2. 用户执行 `wfmctl bind --server <url> --token <token>`。
3. 客户端调用后端 bind API。
4. 后端校验 token，生成或轮换节点 MQTT 凭据。
5. 客户端写入本地 profile。
6. 如果服务正在运行，客户端尝试重启服务。

绑定 token 是一次性的，过期或使用后不能复用。

完整页面时序、绑定命令生成和页面切换见 [客户端接入时序](/reference/client-lifecycle)。

## MQTT 行为

客户端通过 MQTT 接收：

- 配置下发。
- 控制命令。
- 探测请求。

客户端会上报：

- 心跳。
- info。
- detect ack。
- control ack。
- config push ack。

MQTT 断开和重连成功会写日志；检测和重试过程本身不持续刷日志。

完整 topic、payload、ACK、LWT 和在线投影见 [MQTT 消息参考](/reference/mqtt-messages)。后端实现边界见 [MQTT 协议](./mqtt-protocol)。

## WireGuard / AmneziaWG

客户端需要调用本机工具链：

- WireGuard：`wg`、`wireguard.exe`、`wg-quick`。
- AmneziaWG：`awg`、`amneziawg.exe`、`awg-quick`。

Windows 启停隧道走 GUI 工具链能力；Linux/macOS 更依赖 `wg-quick` / `awg-quick`，生命周期命令也主要在这两个平台生效。

WireGuard 与 AmneziaWG 参数规则见 [协议参数参考](/reference/protocols)。端口转发依赖生命周期命令，规则见 [端口转发](/usage/port-forward)。

## 日志原则

日志应记录关键状态变化：

- 服务启动和停止。
- profile 加载。
- MQTT 连接和断开。
- 配置下发结果。
- 控制命令结果。
- WireGuard/AmneziaWG 执行错误。

不要把高频重试、轮询或检测过程持续写入日志。

## 相关文档

- [客户端接入时序](/reference/client-lifecycle)
- [MQTT 消息参考](/reference/mqtt-messages)
- [协议参数](/reference/protocols)
- [API 契约](./api-contract)
- [客户端与控制](/usage/client)
