# api

`src/app/api/` 负责 HTTP 和 SSE 入口。

## 当前边界

- 正式业务接口统一收口到 `/api/v1`
- 开发测试接口单独放到 `/api/v0`，不参与正式业务契约
- 基础设施内部接口单独收口到 `/api/internal`
- 路由只负责请求绑定、响应输出、错误抛转
- 业务规则放到 `repositories/` 和 `services/`
- 实时推送统一走 `/api/v1/events/stream`

## 当前模块

- `__init__.py`：标记 `api` 为包，不承载业务逻辑。
- `v1/router.py` 聚合版本路由
- `v0/router.py` 聚合开发测试路由
- `internal/router.py` 聚合内部基础设施路由
- `v1/routers/auth.py` 认证与会话
- `v1/routers/configs.py` 配置
- `v1/routers/nodes.py` 节点
- `v1/routers/mesh.py` Peer Link / Mesh / WireGuard 预览
- `v1/routers/endpoints.py` 同步状态、运行态、端点控制
- `v1/routers/settings.py` 界面偏好、MQTT 公网引导参数与密码修改
- `v1/routers/backups.py` 快照备份恢复
- `v1/routers/system.py` 健康检查、系统状态、SSE 实时流
- `internal/routers/emqx.py` EMQX HTTP Authorization 回查
- `v0/routers/dev.py` 初始化态重置等开发测试能力

## 目录索引

- [v0/README.md](D:/wenjian/stepsave/project/wg-free-mesh/src/app/api/v0/README.md)
- [v0/routers/README.md](D:/wenjian/stepsave/project/wg-free-mesh/src/app/api/v0/routers/README.md)
- [internal/README.md](D:/wenjian/stepsave/project/wg-free-mesh/src/app/api/internal/README.md)
- [v1/README.md](D:/wenjian/stepsave/project/wg-free-mesh/src/app/api/v1/README.md)
- [v1/routers/README.md](D:/wenjian/stepsave/project/wg-free-mesh/src/app/api/v1/routers/README.md)
