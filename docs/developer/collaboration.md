# 协作约定

本页约束开发者和自动化编码助手的协作行为。目标是减少误操作、减少文档漂移，并保持业务边界稳定。

修改代码前建议先读 [开发者索引](./)、[目录与边界](./project-structure) 和与本次任务对应的参考页。

## 基本原则

- 先读文档和现有代码，再判断实现方式。
- 后端是业务真相来源，前端只负责展示、输入、交互和调用。
- 数据库结构变化必须有 Alembic 迁移。
- 影响用户行为、API、协议、Docker、数据结构或安全策略的变更必须同步文档。
- 不要把临时文件、缓存目录、构建产物或依赖缓存落入工作区。

## 自动化助手限制

自动化助手不得擅自：

- 启动后端、前端、Docker、EMQX、数据库或客户端 agent。
- 执行构建命令。
- 安装、升级、卸载依赖或改变本机环境。
- 绕过权限不足问题。
- 删除用户未明确要求删除的数据。

遇到权限不足时，应申请提权并说明用途。不得通过临时目录、脚本绕行或改变环境来规避。

## 文档同步

以下变更必须同步文档：

- 新增或修改功能页面。
- 新增或修改环境变量。
- Docker compose、Dockerfile、gateway 或反向代理行为变化。
- API、MCP、MQTT、SSE 协议变化。
- 客户端命令和安装行为变化。
- 快照内容和恢复语义变化。
- 安全边界变化。

## 镜像发布

App 镜像由 GitHub Actions 构建并发布到 GHCR：

```text
ghcr.io/xinghenluyus/wg-free-mesh-app
```

版本来源仍然只有一个：`src/pyproject.toml` 的 `[project].version`。

发布规则：

- 只支持 `x.y.z` 和 `x.y.z-rc.n` 两种版本格式；其它格式直接跳过镜像构建。
- 镜像版本标签直接使用 `src/pyproject.toml` 的版本号，例如 `1.0.0` 或 `1.0.0-rc.1`。
- 不发布 `dev`、`sha-*` 或其它临时镜像标签。
- 如果版本是正式版，镜像同时更新 `latest`。
- 如果版本是 RC，且仓库里还没有任何 `vX.Y.Z` 正式版 Git tag，镜像同时更新 `latest`。
- 如果版本是 RC，且仓库里已经存在正式版 Git tag，只发布 RC 版本标签，不更新 `latest`。
- 如果 workflow 由 Git tag 触发，Git tag 必须是 `v<version>`；不一致时跳过镜像构建。
- Docker compose 默认拉取 `latest`，生产环境可在 `.env` 中用 `WFM_IMAGE_TAG` 固定版本。

首次发布后需要在 GitHub Packages 中确认该镜像为 Public，否则外部用户无法匿名拉取。

本地 Docker build 只用于开发调试，compose 中保留注释配置，不作为普通部署入口。

## 前后端协作

前端如果发现需要复杂推导，应优先要求后端提供投影或字段。不要在前端复制：

- 在线状态判断。
- Mesh 拓扑校验。
- 同步状态判断。
- 产物缓存状态。
- EMQX 状态。

## Git 和工作区

工作区可能存在用户未提交修改。不要回滚、覆盖或清理与当前任务无关的文件。

如果需要删除、移动或大规模重写文件，应先确认这些文件是否属于当前任务，并确保不会误删用户内容。

## 常用入口

- 代码边界：[目录与边界](./project-structure)
- API 行为：[API 契约](./api-contract) 与 [API 参考](/reference/api)
- MQTT 通信：[MQTT 协议](./mqtt-protocol) 与 [MQTT 消息参考](/reference/mqtt-messages)
- SSE 实时刷新：[实时事件](./events) 与 [实时事件参考](/reference/realtime)
- 数据结构：[数据库](./database) 与 [数据模型参考](/reference/data-model)
- 安全策略：[安全边界](/reference/security)
