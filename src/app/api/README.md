# api

`src/app/api/` 负责 HTTP 和 WebSocket 入口。

## 当前边界

- 所有后端接口统一收口到 `/api/v1`
- 路由只负责请求绑定、响应输出、错误抛转
- 业务规则放到 `repositories/` 和 `services/`
- 实时推送统一走 `/api/v1/ws/events`

## 当前模块

- `v1/router.py` 聚合版本路由
- `v1/routers/auth.py` 认证与会话
- `v1/routers/configs.py` 配置
- `v1/routers/nodes.py` 节点
- `v1/routers/mesh.py` Peer Link / Mesh / WireGuard 预览
- `v1/routers/endpoints.py` 同步状态、运行态、端点控制
- `v1/routers/settings.py` MQTT 公网引导参数与密码修改
- `v1/routers/backups.py` 快照备份恢复
- `v1/routers/system.py` 健康检查、系统状态、WebSocket
