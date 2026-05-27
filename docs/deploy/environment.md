# 环境变量

部署前先复制 `.env.example`，再修改 `.env`。不要直接用示例值上线。

```bash
cp .env.example .env
```

这个页面只列启动前必须关注的变量。完整变量说明见 [环境变量参考](/reference/env)。

## 必须修改

### 正式访问地址

```env
WFM_PUBLIC_ORIGIN=https://wfm.example.com
```

这是系统的主访问来源。控制台、API、SSE、MCP 和客户端绑定配置都会以它为准。生产环境应填写 HTTPS 地址。

本机测试可以保留：

```env
WFM_PUBLIC_ORIGIN=http://localhost:8000
```

### EMQX 密码

```env
WFM_EMQX_USERNAME=admin
WFM_EMQX_PASSWORD=change-me
```

`WFM_EMQX_PASSWORD` 同时用于 EMQX Dashboard、管理 API 和服务端 MQTT 超级用户。生产环境必须改成高强度密码。

### EMQX 授权共享密钥

```env
WFM_EMQX_AUTHZ_SHARED_KEY=change-me-long-random-secret
```

EMQX 会通过这个密钥回调后端做 topic 授权。生产环境必须改成随机长密钥。

### EMQX 节点 Cookie

```env
WFM_EMQX_NODE_COOKIE=change-me-emqx-cookie
```

单节点部署也建议修改。多节点 EMQX 集群时，各节点必须一致。

### PostgreSQL 密码

PostgreSQL 部署还必须修改：

```env
WFM_POSTGRES_PASSWORD=change-me
WFM_DATABASE=postgresql+psycopg://wfm:change-me@postgres:5432/wfm
```

`WFM_DATABASE` 里的密码要和 `WFM_POSTGRES_PASSWORD` 保持一致。

## 开发开关

生产环境保持关闭：

```env
WFM_DEBUG=false
WFM_ENABLE_DEV_TEST_API=false
```

`WFM_ENABLE_DEV_TEST_API=true` 会跳过正式来源限制并暴露开发测试接口，只能用于本地开发。

## 额外允许来源

如果生产入口是 `https://wfm.example.com`，但需要临时允许本地调试前端访问后端，可以配置：

```env
WFM_EXTRA_ALLOWED_ORIGINS=["http://localhost:5173"]
```

这只扩展 Origin，不扩展 Host。正式入口仍由 `WFM_PUBLIC_ORIGIN` 控制。

## MQTT 开关

启用客户端绑定、远程控制和端点在线能力：

```env
WFM_ENABLE_MQTT_SERVICES=true
COMPOSE_PROFILES=mqtt
```

完全关闭 MQTT：

```env
WFM_ENABLE_MQTT_SERVICES=false
COMPOSE_PROFILES=
```

关闭后，客户端绑定、端点控制、MQTT 状态和相关接口都会被系统层面禁用。

## MQTT TLS

```env
WFM_MQTT_TLS_ENABLED=true
WFM_MQTT_PUBLIC_PORT=1883
WFM_MQTT_PUBLIC_TLS_PORT=8883
```

`WFM_MQTT_TLS_ENABLED=true` 会开启客户端 TLS listener，并把客户端绑定配置默认引导到 TLS 端口。后端连接 EMQX 仍默认走 Docker 网络内明文地址。

## 下一步

- 继续启动：回到 [Docker 部署](/deploy/)。
- 生产暴露：阅读 [反向代理](/deploy/reverse-proxy)。
- 查完整变量：阅读 [环境变量参考](/reference/env)。
