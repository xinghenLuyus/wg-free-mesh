# WG Free Mesh 重构文档索引

当前文档已经从“技术栈骨架”切换到“恢复旧系统控制平面能力”的轨道，并开始补齐 `wfm` 客户端方案。

## 当前重点

- 先用文档固化接口契约，再同步改前后端
- 恢复配置、节点、Mesh、配置生成、端点控制、备份恢复主流程
- 客户端进入架构设计阶段，先固化 `wfm-agent + wfmctl` 模型
- 生产部署改为前端构建 `dist` 后由 FastAPI 统一托管
- 本地开发继续前后端双开

## 文档导航

- [总体架构](D:/wenjian/stepsave/project/wg-free-mesh/docs/总体架构.md)
- [目录结构规划](D:/wenjian/stepsave/project/wg-free-mesh/docs/目录结构规划.md)
- [后端设计](D:/wenjian/stepsave/project/wg-free-mesh/docs/后端设计.md)
- [前端设计](D:/wenjian/stepsave/project/wg-free-mesh/docs/前端设计.md)
- [客户端设计](D:/wenjian/stepsave/project/wg-free-mesh/docs/客户端设计.md)
- [MQTT集成设计](D:/wenjian/stepsave/project/wg-free-mesh/docs/MQTT集成设计.md)
- [前后端职责边界](D:/wenjian/stepsave/project/wg-free-mesh/docs/前后端职责边界.md)
- [安全边界](D:/wenjian/stepsave/project/wg-free-mesh/docs/安全边界.md)
- [API契约原则](D:/wenjian/stepsave/project/wg-free-mesh/docs/API契约原则.md)
- [API接口设计](D:/wenjian/stepsave/project/wg-free-mesh/docs/API接口设计.md)
- [实时事件设计](D:/wenjian/stepsave/project/wg-free-mesh/docs/实时事件设计.md)
- [迁移计划](D:/wenjian/stepsave/project/wg-free-mesh/docs/迁移计划.md)
- [协作约定](D:/wenjian/stepsave/project/wg-free-mesh/docs/协作约定.md)
- [旧系统功能梳理](D:/wenjian/stepsave/project/wg-free-mesh/docs/旧系统功能梳理.md)
- [重构差距清单](D:/wenjian/stepsave/project/wg-free-mesh/docs/重构差距清单.md)

## 当前目录边界

- `src/` 后端
- `front/` 前端
- `client/` 客户端预留
- `docs/` 重构文档
- `docker/` 容器与部署
- `bak/` 旧代码参考，不参与版本管理
