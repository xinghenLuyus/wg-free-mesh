# MQTT 协议

MQTT 用于服务端和客户端之间的低流量控制通道。它承载在线状态、配置下发、控制命令、探测和 ACK。

如果你要改 topic、payload 或在线判定，必须同时看 [MQTT 消息参考](/reference/mqtt-messages)、[客户端接入时序](/reference/client-lifecycle) 和 [客户端](./client)。

## 角色

| 角色 | 职责 |
| --- | --- |
| 后端 | 数据库真相来源、MQTT 管理者、命令发布者、ACK 处理者。 |
| EMQX | MQTT broker、客户端认证和 topic 授权执行层。 |
| wfm-agent | 客户端服务，订阅命令、执行本机动作、上报状态。 |

后端永远以数据库为真相。EMQX 在线时同步账号和授权；EMQX 离线时先落库，恢复后统一同步。

## Topic 方向

Topic 以节点身份隔离。客户端只能访问自己的 topic，服务端拥有管理和发布权限。

常见方向：

- 服务端到客户端：配置下发、控制命令、探测。
- 客户端到服务端：心跳、info、event、ACK。

具体 topic、payload、ACK、LWT 和在线投影见 [MQTT 消息参考](/reference/mqtt-messages)。动态端点从绑定到上线的完整页面和后端时序见 [客户端接入时序](/reference/client-lifecycle)。

## 消息类型

常见消息：

- `config/push`：下发期望配置。
- `control`：执行 start、stop、push_config、wg_show。
- `detect`：探测客户端状态。
- `info`：客户端版本、工具链和本机能力。
- `event`：客户端主动事件。
- `heartbeat`：低频心跳。
- `ack`：对命令或配置下发的回执。

## 在线状态

在线状态不是单一心跳判断。规则是：

- 收到明确离线信号时，一定离线。
- 没有离线信号时，只要任一有效在线条件成立，就可以视为在线。
- 有效条件包括 MQTT 连接、控制命令响应、detect 回执和近期状态上报。

客户端心跳可以低频，目的是节约流量；连接断开后由 MQTT 客户端自动重连。

## TLS 边界

后端默认通过 Docker 内网明文连接 EMQX。客户端是否使用 TLS 由部署和绑定配置决定。

`WFM_MQTT_TLS_ENABLED` 影响客户端 MQTT listener 和客户端绑定配置，不强制后端连接使用 TLS。若部署者显式把 `WFM_MQTT_URL` 配成 `mqtts://`，后端才会按该地址连接。

## 授权

EMQX 通过内部授权回调向后端确认 topic 权限。共享密钥由部署环境配置。

重置客户端时，后端会删除或禁用对应 EMQX 用户，并尝试断开客户端连接。

内部回调接口见 [API 参考](/reference/api)，安全边界见 [安全边界](/reference/security)，环境变量见 [环境变量参考](/reference/env)。

## 相关文档

- [MQTT 消息参考](/reference/mqtt-messages)
- [客户端接入时序](/reference/client-lifecycle)
- [客户端](./client)
- [后端](./backend)
- [实时事件](./events)
