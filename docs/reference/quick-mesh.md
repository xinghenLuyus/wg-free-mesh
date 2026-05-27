# 快速组网

快速组网会删除指定配置下已有 Mesh 对，然后按所选模式重新生成。

## 公共参数

| 字段 | 说明 |
| --- | --- |
| `mode` | `hub_spoke`、`full_mesh` 或 `free_mesh`。 |
| `endpoint_ref_family` | 使用 `ipv4` 或 `ipv6` 公网入口。 |
| `use_preshared_key` | 是否为生成的 Mesh 对启用 PSK。 |

## 网关节点式网络

`hub_spoke` 使用一个 gateway 端点作为中心。

要求：

- 至少两个启用端点。
- gateway 必须启用。
- gateway 必须有对应地址族公网入口。

AllowedIPs 规则：

- gateway 指向 leaf：使用 leaf 的虚拟 IP。
- leaf 指向 gateway：使用整个配置虚拟网段，保证 leaf 之间通过 gateway 互通。

## 全连接网络

`full_mesh` 让所有启用且有公网入口的端点两两直连。

要求：

- 至少两个启用端点。
- 每个参与端点都需要对应地址族公网入口。

AllowedIPs 通常为对端虚拟 IP。

## Free Mesh

`free_mesh` 允许多个 gateway 组成全连接网络，leaf 挂载到某个 gateway 下方。

要求：

- 至少一个 gateway。
- gateway 必须是启用端点。
- gateway 必须有对应地址族公网入口。
- 每个启用端点必须被分配为 gateway 或 leaf。
- 同一个端点不能同时是 gateway 和 leaf。
- leaf 的 gateway 必须在 gateway 集合中。

AllowedIPs 规则：

- gateway 与 gateway：互相写对端虚拟 IP，并承担骨干互联。
- leaf 指向所属 gateway：写整个配置虚拟网段，让 leaf 能访问全网。
- gateway 指向直属 leaf：写 leaf 虚拟 IP。
- 非直属 leaf 的可达性通过 gateway 骨干转发实现。
