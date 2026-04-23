# mqtt

`internal/mqtt` 负责 Go 客户端和 EMQX 的运行期连接。

当前阶段只打通通信底座：

- 连接 broker
- 发布 `event`
- 发布 `heartbeat`
- 订阅 `config/push`、`control`、`detect`
- 返回对应 ACK

