# profile

`internal/profile` 管理 Go 客户端本地 profile 文件。

`wfmctl bind` 负责写入 profile，`wfm-agent` 负责读取所有 profile 并为每个 profile 建立独立 MQTT 会话。

