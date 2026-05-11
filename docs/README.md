# WG Free Mesh 重构文档索引

当前文档记录的是重构完成后的系统边界、接口契约和运行约束。历史参考目录已移除，后续以当前源码和本文档为准。

## 当前重点

- 配置、节点、Mesh、配置生成、端点控制、备份恢复主流程已落地
- 客户端采用 `wfm-agent + wfmctl` 模型，绑定、MQTT 通信、心跳、命令 ACK 和服务管理骨架已落地
- 下载工具统一从“下载”入口进入，客户端下载和配置批量下载由后端负责产物生成与分发
- 生产部署改为前端构建 `dist` 后由 FastAPI 统一托管
- 本地开发继续前后端双开

## 文档导航

- [总体架构](D:/wenjian/stepsave/project/wg-free-mesh/docs/总体架构.md)
- [目录结构规划](D:/wenjian/stepsave/project/wg-free-mesh/docs/目录结构规划.md)
- [后端设计](D:/wenjian/stepsave/project/wg-free-mesh/docs/后端设计.md)
- [前端设计](D:/wenjian/stepsave/project/wg-free-mesh/docs/前端设计.md)
- [客户端设计](D:/wenjian/stepsave/project/wg-free-mesh/docs/客户端设计.md)
- [MQTT集成设计](D:/wenjian/stepsave/project/wg-free-mesh/docs/MQTT集成设计.md)
- [MQTT消息协议设计](D:/wenjian/stepsave/project/wg-free-mesh/docs/MQTT消息协议设计.md)
- [客户端接入时序设计](D:/wenjian/stepsave/project/wg-free-mesh/docs/客户端接入时序设计.md)
- [前后端职责边界](D:/wenjian/stepsave/project/wg-free-mesh/docs/前后端职责边界.md)
- [安全边界](D:/wenjian/stepsave/project/wg-free-mesh/docs/安全边界.md)
- [API契约原则](D:/wenjian/stepsave/project/wg-free-mesh/docs/API契约原则.md)
- [API接口设计](D:/wenjian/stepsave/project/wg-free-mesh/docs/API接口设计.md)
- [实时事件设计](D:/wenjian/stepsave/project/wg-free-mesh/docs/实时事件设计.md)
- [迁移计划](D:/wenjian/stepsave/project/wg-free-mesh/docs/迁移计划.md)
- [协作约定](D:/wenjian/stepsave/project/wg-free-mesh/docs/协作约定.md)

## 当前目录边界

- `src/` 后端
- `front/` 前端
- `client/` Go 客户端
- `docs/` 重构文档
- `docker/` 容器与部署
