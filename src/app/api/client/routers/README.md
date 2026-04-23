# client routers

`app/api/client/routers/` 放置客户端专用 HTTP 初始化接口。

当前只允许客户端在首次绑定时使用 HTTP。绑定成功后，运行期配置下发、控制、心跳、探测和日志都走 MQTT。

## 文件

- `bind.py`：校验一次性绑定 token，创建或轮换节点专属 MQTT 凭据，并返回 Go 客户端所需的本地 profile 初始化数据。

