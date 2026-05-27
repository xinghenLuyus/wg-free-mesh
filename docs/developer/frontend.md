# 前端

前端使用 Vue 3、Vite、TypeScript、Pinia、Vue Router 和 Element Plus。

前端开发前先读 [目录与边界](./project-structure) 的前端职责部分。只要页面需要跨资源推导，优先回到 [后端](./backend) 增加投影。

## 目录入口

| 目录 | 作用 |
| --- | --- |
| `front/src/views` | 页面级视图。 |
| `front/src/components` | 复用组件。 |
| `front/src/api` | API 客户端封装。 |
| `front/src/stores` | Pinia 状态。 |
| `front/src/router` | 路由定义。 |
| `front/src/i18n` | 中英文语言包。 |
| `front/src/types` | 前端接口类型。 |
| `front/src/composables` | 组合式逻辑。 |

## 核心原则

前端只负责展示、输入、交互和调用。以下逻辑不应在前端重复实现：

- 节点在线判断。
- 同步状态判断。
- Mesh 拓扑校验。
- 客户端产物是否存在。
- 快照内容解析。
- EMQX 状态推导。
- MCP 权限判断。

如果页面需要这些结果，应由后端返回字段或投影。

相关稳定字段优先查 [API 参考](/reference/api)、[数据模型](/reference/data-model) 和 [错误码](/reference/errors)。

## 页面组织

主要页面分为：

- 首页：系统概览和配置入口。
- 配置概览：配置、端点、标签和基础状态。
- 节点工作区：Mesh、同步、控制和高级设置。
- 工具列表：下载、快速组网、端口转发、AI 接入。
- 设置页：系统设置、MQTT、备份恢复、密码。

工具型页面应优先围绕用户动作组织，不展示后端内部缓存、文件路径或临时状态。

工具页业务规则可对照 [下载与文件 token](/reference/downloads)、[快速组网](/reference/quick-mesh)、[MCP 参考](/reference/mcp) 和 [快照参考](/reference/snapshot)。

## 实时事件

前端通过 SSE 接收后端事件。页面应把 SSE 当作刷新提示或增量补丁来源，而不是业务真相来源。

常见策略：

- 收到列表级事件后刷新列表。
- 收到页面级事件后刷新当前页面投影。
- 收到控制日志事件后追加或更新日志。

完整事件列表、事件 scope 和订阅策略见 [实时事件参考](/reference/realtime)。

## 国际化

所有可见文案进入 `front/src/i18n/messages`。新增页面、按钮、提示、错误文案时，中英文都要同步。

错误码展示优先使用后端稳定错误码映射，不解析后端错误消息。

## 视觉和交互

这个项目是运维控制台，不是营销页面。页面应保持信息密度、扫描效率和操作清晰度：

- 重要动作靠近业务上下文。
- 批量或危险操作需要明确提示。
- 长耗时操作阻止重复提交。
- 移动端至少保证列表、卡片和表单不重叠。

## 相关文档

- [后端](./backend)
- [API 契约](./api-contract)
- [实时事件](./events)
- [认证与权限](/reference/auth)
- [安全边界](/reference/security)
