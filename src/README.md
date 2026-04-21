# src

`src/` 是本项目的 FastAPI 后端工程。

## 当前范围

- 认证与会话
- 配置管理
- 节点管理
- Peer Link / Mesh 校验
- WireGuard 配置预览
- 系统态与同步态管理
- 端点运行态、控制日志、批量 probe
- SSE 实时事件
- MQTT 公网引导参数设置
- 备份恢复
- 系统状态聚合

客户端 enrollment、`.wgm`、Go Agent 暂缓。

## 认证初始化

后端不会写入默认管理员密码。首次启动后，如果数据库没有有效 `admin` 密码哈希，前端会进入 `/setup` 设置初始密码。

认证使用 Bearer Token：

- `POST /api/v1/auth/setup` 设置初始密码并返回 token。
- `POST /api/v1/auth/login` 登录并返回 token。
- 业务接口需要 `Authorization: Bearer <token>`。
- 修改密码会轮换 token secret，使旧 token 失效。

## Mesh Endpoint 规则

- `ipv4_address` 是公网 IPv4 入口，可填写 IP 或域名。
- `ipv6_address` 是公网 IPv6 入口，可填写 IP 或域名。
- `endpoint_ref_family` 只使用 `ipv4` 或 `ipv6`。
- `endpoint_mode=auto` 为尽力生成：对向对应公网入口存在则写 Endpoint，不存在则留空。
- `endpoint_mode=none` 强制不写 Endpoint。
- `endpoint_mode=manual` 必须填写 Host 和 Port。
- WireGuard Endpoint 只有在 Host 是 IPv6 字面量时才加方括号，域名不加。

可配置项：

```powershell
WFM_DEBUG=true
WFM_CORS_ORIGINS=["http://localhost:5173","http://localhost:8080"]
WFM_MQTT_URL=mqtt://localhost:1883
WFM_AUTH_TOKEN_EXPIRE_MINUTES=1440
WFM_TIMEZONE=Asia/Shanghai
WFM_ENABLE_DEV_TEST_API=false
```

环境变量示例文件放在 [`.env.example`](D:/wenjian/stepsave/project/wg-free-mesh/src/.env.example)，实际本地配置文件应放到 `src/.env`。后端配置不会再从项目根目录读取 `.env`。
时间存储仍统一使用 UTC，控制台默认显示时区由 `WFM_TIMEZONE` 控制，默认值为北京时间 `Asia/Shanghai`。
`WFM_ENABLE_DEV_TEST_API` 默认关闭；只有显式设为 `true` 时，`/api/v0` 开发测试接口才会注册。

## 手动运行

安装依赖：

```powershell
cd src
python -m pip install -e .[dev]
```

开发启动后端：

```powershell
cd src
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --timeout-graceful-shutdown 1
```

说明：

- 当前项目包含 SSE 长连接。
- `fastapi dev` / `fastapi run` 不支持 `--timeout-graceful-shutdown` 参数。
- 为避免浏览器仍然保持连接时拖住后端退出，开发启动命令统一使用 `uvicorn`，并增加 `--timeout-graceful-shutdown 1` 作为停机兜底。


可访问：

- OpenAPI: `http://127.0.0.1:8000/docs`
- 健康检查: `http://127.0.0.1:8000/api/v1/system/health`
- SSE: `http://127.0.0.1:8000/api/v1/events/stream`
- 开发测试重置接口: `http://127.0.0.1:8000/api/v0/dev/reset-bootstrap`

SSE 需要附带 Bearer Token：

```http
GET /api/v1/events/stream HTTP/1.1
Authorization: Bearer <access_token>
```

`/api/v1/events/stream` 会记录连接 ID、客户端地址、用户和连接存活时长，便于定位移动端长连接问题。

开发测试重置接口不要求后台 token，可直接命令行调用：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v0/dev/reset-bootstrap
```

该接口只清初始化态相关设置：

- 管理员密码哈希
- 登录 token secret
- 密码更新时间
- `ui_locale`
- `ui_theme_mode`

不会删除配置、节点、Mesh 关系和业务快照。

## 测试

```powershell
cd src
python -m pytest -q
```

## 生产说明

- 生产态由 FastAPI 同时提供 API 和前端静态资源
- FastAPI 优先读取根目录 `front/dist`
- Docker 镜像会先构建前端，再把 `dist` 复制进后端镜像
- 生产启动命令同样带 `--timeout-graceful-shutdown 1`，避免 SSE 长连接阻塞停机

## 目录索引

- [app/README.md](D:/wenjian/stepsave/project/wg-free-mesh/src/app/README.md)：应用主包入口。
- [app/api/README.md](D:/wenjian/stepsave/project/wg-free-mesh/src/app/api/README.md)：API 分层说明。
- [app/core/README.md](D:/wenjian/stepsave/project/wg-free-mesh/src/app/core/README.md)：配置、安全、错误和响应。
- [app/domain/README.md](D:/wenjian/stepsave/project/wg-free-mesh/src/app/domain/README.md)：领域模型。
- [app/infrastructure/README.md](D:/wenjian/stepsave/project/wg-free-mesh/src/app/infrastructure/README.md)：数据库与文件路径。
- [app/repositories/README.md](D:/wenjian/stepsave/project/wg-free-mesh/src/app/repositories/README.md)：仓储实现与命名规则。
- [app/schemas/README.md](D:/wenjian/stepsave/project/wg-free-mesh/src/app/schemas/README.md)：请求与响应模型。
- [app/services/README.md](D:/wenjian/stepsave/project/wg-free-mesh/src/app/services/README.md)：认证、控制平面与实时服务。
- [tests/README.md](D:/wenjian/stepsave/project/wg-free-mesh/src/tests/README.md)：后端测试说明。
