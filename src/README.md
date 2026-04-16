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
- WebSocket 实时事件
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
WFM_AUTH_TOKEN_EXPIRE_MINUTES=1440
```

## 手动运行

安装依赖：

```powershell
cd src
python -m pip install -e .[dev]
```

启动后端：

```powershell
cd src
python -m fastapi dev app/main.py --host 127.0.0.1 --port 8000
```

可访问：

- OpenAPI: `http://127.0.0.1:8000/docs`
- 健康检查: `http://127.0.0.1:8000/api/v1/system/health`
- WebSocket: `ws://127.0.0.1:8000/api/v1/ws/events`

WebSocket 需要附带 token：

```text
ws://127.0.0.1:8000/api/v1/ws/events?token=<access_token>
```

## 测试

```powershell
cd src
python -m pytest -q
```

## 生产说明

- 生产态由 FastAPI 同时提供 API 和前端静态资源
- FastAPI 优先读取根目录 `front/dist`
- Docker 镜像会先构建前端，再把 `dist` 复制进后端镜像
