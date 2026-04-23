# client API

`app/api/client/` 承载客户端专用 HTTP 初始化接口。

边界：

- 这里只允许首次绑定使用 HTTP。
- 绑定成功后，客户端运行期通信全部走 MQTT。
- 本目录接口不使用后台管理员 session token，而是使用 5 分钟一次性 bind token。

当前入口：

- `POST /api/client/v1/bind`
  - 校验 bind token。
  - 创建或轮换节点专属 MQTT 凭据。
  - 将凭据同步到 EMQX。
  - 返回 Go 客户端本地 profile 初始化数据。

