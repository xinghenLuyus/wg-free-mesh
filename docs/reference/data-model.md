# 数据模型

本页描述核心领域对象，字段以业务语义为主。

## Config

配置是 Mesh 的根对象。

| 字段 | 说明 |
| --- | --- |
| `id` | 配置 ID，形如 `cfg_xxx`。 |
| `name` | 配置名称，也会影响生成的接口名。 |
| `virtual_subnet` | Mesh 虚拟网段。 |
| `default_listen_port` | 新端点默认监听端口。 |
| `default_mtu` | 默认 MTU。 |
| `default_dns` | 默认 DNS。 |
| `auto_sync` | 只影响新建端点的默认自动同步值。 |
| `tunnel_protocol` | `wireguard` 或 `amneziawg_2`。 |
| `awg_s1..awg_s4` | AmneziaWG 配置级 S 参数。 |
| `awg_h1..awg_h4` | AmneziaWG 配置级 H 参数。 |

## Node

端点代表加入 Mesh 的设备。

| 字段 | 说明 |
| --- | --- |
| `id` | 端点 ID，形如 `node_xxx`。 |
| `config_id` | 所属配置。 |
| `name` | 端点名称。 |
| `ipv4_address` | 公网 IPv4 或域名。 |
| `ipv6_address` | 公网 IPv6 或域名。 |
| `listen_port` | 端点监听端口。 |
| `virtual_ip` | Mesh 虚拟 IP。 |
| `node_type` | `dynamic` 或 `static`。 |
| `auto_sync` | 是否允许自动同步。 |
| `pre_up/post_up/pre_down/post_down` | 生命周期命令。 |
| `awg_jc/awg_jmin/awg_jmax` | AmneziaWG 端点本地扰动参数。 |
| `awg_i1..awg_i5` | AmneziaWG CPS 伪装包参数。 |

## PeerLink

Mesh 对是双向关系中的单向记录。一个双向 Mesh 对由同一个 `link_group_id` 下的 forward 和 reverse 两条记录组成。

| 字段 | 说明 |
| --- | --- |
| `local_node_id` | 本端端点。 |
| `peer_node_id` | 对端端点。 |
| `allowed_ips` | 写入 Peer 的 AllowedIPs。 |
| `persistent_keepalive` | PersistentKeepalive。 |
| `preshared_key` | PSK，可为空。 |
| `endpoint_mode` | `auto`、`manual` 或 `none`。 |
| `endpoint_ref_family` | 自动 Endpoint 使用 `ipv4` 或 `ipv6`。 |
| `endpoint_port_mode` | 使用对端监听端口或手动端口。 |

## NodeConfigState

同步态分为：

- `desired`：系统根据当前配置生成的目标态。
- `staged`：待下发给客户端的同步态。
- `confirmed`：客户端确认已应用的状态。

## EndpointRuntimeStatus

运行态记录动态端点的在线、隧道和同步状态。

在线判断以服务端运行态为准。离线信号收到后一定离线；否则只要心跳、探测、控制通道等任一在线条件成立即可视为在线。

## PortForwardRule

端口转发规则由工具管理。

| 字段 | 说明 |
| --- | --- |
| `from_node_id` | From 端点，也就是源端点，服务真实存在的位置。 |
| `from_port` | From 端口，也就是源端口，服务真实监听的端口。 |
| `to_node_id` | To 端点，也就是目的端点，承接访问并持有生命周期命令。 |
| `to_port` | To 端口，也就是目的端口，对外暴露的访问端口。 |
| `to_platform` | `linux` 或 `darwin`。 |
| `protocol` | `tcp`、`udp` 或 `all`。 |
