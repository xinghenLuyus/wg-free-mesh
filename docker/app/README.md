# app

`docker/app/` 保存后端镜像构建文件。

## 当前内容

- `backend.Dockerfile`

## 说明

- 前端构建已经收进 `backend.Dockerfile` 多阶段构建
- 前端静态资源使用构建机原生架构生成，运行镜像仍按目标架构构建，支持 `linux/amd64` 和 `linux/arm64`。
- Docker 编排中的 MQTT broker 由 [docker/emqx/README.md](../emqx/README.md) 管理
