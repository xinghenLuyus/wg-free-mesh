# 协议参数

WG Free Mesh 支持 WireGuard 和 AmneziaWG。AWG 在配置创建和配置设置页独立选择 1.5、2.0 或 3.1，整个 Mesh 使用同一版本。工具链要求见 [AWG 协议适配说明](/help/awg-compatibility)。

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

## AmneziaWG

AmneziaWG 工具链和 WireGuard 基本一致，命令名前缀增加 `a`：

- `wg` -> `awg`
- `wg-quick` -> `awg-quick`

Windows 下使用 `amneziawg.exe` 代替 `wireguard.exe`。

## 配置级 AWG 参数

配置级参数在同一个 Mesh 内统一。

| 字段 | 说明 | 规则 |
| --- | --- | --- |
| `awg_s1` | Init 包随机前缀长度 | `0..65535` |
| `awg_s2` | Response 包随机前缀长度 | `0..65535` |
| `awg_s3` | Cookie 包随机前缀长度 | `0..65535` |
| `awg_s4` | Data 包随机前缀长度 | `0..65535` |
| `awg_h1` | Init 动态 header 范围 | `uint32` 单值或 `start-end` |
| `awg_h2` | Response 动态 header 范围 | `uint32` 单值或 `start-end` |
| `awg_h3` | Cookie 动态 header 范围 | `uint32` 单值或 `start-end` |
| `awg_h4` | Data 动态 header 范围 | `uint32` 单值或 `start-end` |

`H1..H4` 范围不能相互重叠。

1.5 只输出 S1/S2，S3/S4 必须为 0；H1–H4 必须是固定值，且 S1 + 56 不能等于 S2。2.0 和 3.1 支持全部 S 和 H 范围。

3.1 配置扩展字段位于 `awg_options`：`header_protection_key` 对应 `HeaderProtectionKey`，为非全零的 32 字节 Base64 密钥；显式传 `null` 可停用。启用时 S1–S4 必须至少为 12。

共享 `random_trailers` 为 `on/off` 开关，启用时 S1–S4 必须相等。保存共享开关会统一更新各端点；未设置共享值时使用端点同名参数。

## 端点级 AWG 参数

端点级参数可每个端点不同。

| 字段 | 说明 | 规则 |
| --- | --- | --- |
| `awg_jc` | Junk 包数量 | `0..65535` |
| `awg_jmin` | Junk 最小长度 | `0..65535` |
| `awg_jmax` | Junk 最大长度 | `0..65535` 且大于 `Jmin` |
| `awg_i1..awg_i5` | CPS 伪装包链 | 文本表达式 |

新建端点或首次切换 AWG 时补齐缺失参数；日常保存允许清空，清空的参数不自动填充。

端点扩展字段同样位于 `awg_options`：

| 版本 | 字段 | 规则 |
| --- | --- | --- |
| 1.5 | `j1`、`j2`、`j3` | CPS 表达式，输出为 J1–J3。 |
| 1.5 | `itime` | `uint32`，输出为 Itime。 |
| 3.1 | `content_padding_addition`、`rekey_after_time`、`rekey_timeout`、`reject_after_time`、`keepalive_timeout`、`max_handshake_attempts` | `0..65535` 的单值或 `start-end`；RejectAfterTime 的非零下界必须大于 RekeyAfterTime 的非零上界。 |
| 3.1 | `disable_cookies` | 布尔值，输出为 `on/off`，生成时保持已设置的值。 |

输出名称对应工具链的 CamelCase 参数，例如 `RekeyAfterTime`。留空不输出；当前版本不支持的已存扩展参数保留但不输出，新增或改写不支持的参数会报错。

## 随机策略

统一生成选择方向 `generic/dns/stun/rtp/quic` 和强度 `low/balanced/high`。策略以 `_random_direction/_random_intensity` 存入配置 options，只影响显式生成和新端点初始化，绝不覆盖已保存的具体参数。

| 强度 | S 随机上限 | Jc | Jmin | Jmax 上限 | I 包数（QUIC 除外） |
| --- | --- | --- | --- | --- | --- |
| low | 24 | 1–3 | 64–255 | 256 | 1 |
| balanced | 48 | 4–7 | 64–256 | 768 | 3 |
| high | 96 | 8–10 | 64–256 | 1024 | 5 |

S 下限为 0，3.1 启用 HP 时为 12，3.1 生成相等的 S1–S4；1.5 的 S3/S4 为 0。H 在 uint32 内随机生成互不重叠范围（2.0）或固定值（1.5/3.1）。Jmax 严格大于 Jmin。各端点分别使用系统安全随机源生成 J/I、适用的填充/时序或 J1–J3/Itime 参数，不保证每个端点绝无偶然重复。

QUIC 仅生成一个 1200 字节 Initial。其它方向生成对应结构的握手前签名包；未使用的 I 字段为空。生成保留已设置的 HP 密钥和机制开关。所有适用字段可手动编辑，推荐随机范围不是手工上限；大包与激进时序需自行评估实际网络。方向能力边界见 [AWG 协议适配说明](/help/awg-compatibility)。
