# docker

`docker/` 现在采用单应用镜像方案：

- 前端在镜像构建阶段执行 `pnpm run build`
- 产物复制到后端镜像
- FastAPI 同时提供 API 和前端静态资源
- MQTT 仍保留单独容器

## 启动

```powershell
cd docker
docker compose up --build
```

访问：

- 应用: `http://127.0.0.1:8000`
- MQTT: `mqtt://127.0.0.1:1883`

## 本地开发

本地继续分开跑：

后端：

```powershell
cd src
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --timeout-graceful-shutdown 1
```

前端：

```powershell
cd front
pnpm run dev
```
