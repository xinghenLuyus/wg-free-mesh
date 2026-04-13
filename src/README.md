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

## 测试

```powershell
cd src
python -m pytest -q
```

## 生产说明

- 生产态由 FastAPI 同时提供 API 和前端静态资源
- FastAPI 优先读取根目录 `front/dist`
- Docker 镜像会先构建前端，再把 `dist` 复制进后端镜像
