# 协议参数

WG Free Mesh 支持 WireGuard 和 AmneziaWG 2.0。配置创建和配置设置页选择协议。

## WireGuard

WireGuard 不使用额外 AWG 参数。

生成配置时使用：

- `[Interface]`
- `[Peer]`
- `PrivateKey`
- `Address`
- `ListenPort`
- `MTU`
- `DNS`
- `AllowedIPs`
- `Endpoint`
- `PersistentKeepalive`
- `PresharedKey`

## AmneziaWG 2.0

AmneziaWG 工具链和 WireGuard 基本一致，命令名前缀增加 `a`：

- `wg` -> `awg`
- `wg-quick` -> `awg-quick`

Windows 下使用 `amneziawg.exe` 代替 `wireguard.exe`。

## 配置级 AWG 参数

配置级参数在同一个 Mesh 内统一。

| 字段 | 说明 | 规则 |
| --- | --- | --- |
| `awg_s1` | Init 包随机前缀长度 | `0..64` |
| `awg_s2` | Response 包随机前缀长度 | `0..64` |
| `awg_s3` | Cookie 包随机前缀长度 | `0..64` |
| `awg_s4` | Data 包随机前缀长度 | `0..32` |
| `awg_h1` | Init 动态 header 范围 | `uint32` 单值或 `start-end` |
| `awg_h2` | Response 动态 header 范围 | `uint32` 单值或 `start-end` |
| `awg_h3` | Cookie 动态 header 范围 | `uint32` 单值或 `start-end` |
| `awg_h4` | Data 动态 header 范围 | `uint32` 单值或 `start-end` |

`H1..H4` 范围不能相互重叠。

## 端点级 AWG 参数

端点级参数可每个端点不同。

| 字段 | 说明 | 规则 |
| --- | --- | --- |
| `awg_jc` | Junk 包数量 | `0..10` |
| `awg_jmin` | Junk 最小长度 | `64..1024` |
| `awg_jmax` | Junk 最大长度 | `64..1024` 且大于 `Jmin` |
| `awg_i1..awg_i5` | CPS 伪装包链 | 文本表达式 |

留空时后端会随机生成。

## 随机策略

后端随机生成：

- `S1..S3`：`15..64`
- `S4`：`0..32`
- `H1..H4`：`1024..4294967295` 内随机非重叠范围
- `Jc`：`4..10`
- `Jmin`：`64..256`
- `Jmax`：大于 `Jmin`，最大 `1024`
- `I1..I5`：DNS-like、STUN-like 或 QUIC-like 模板
