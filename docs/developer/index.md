# 开发者文档

这一组文档面向维护者和二次开发者，说明 WG Free Mesh 的内部边界、模块职责和协作规则。

如果你只是部署和使用系统，优先阅读 [指南](/guide/) 和 [功能](/usage/)。如果你准备修改后端、前端、客户端、数据库结构、MQTT 协议或 MCP 能力，再从这里开始。

## 阅读顺序

建议按下面顺序阅读：

1. [总体架构](./architecture)：先理解系统由哪些进程和组件组成。
2. [目录与边界](./project-structure)：确认源码目录、运行数据和职责边界。
3. [后端](./backend)：理解业务规则放在哪里，API、服务、仓储如何分层。
4. [数据库](./database)：理解 SQLAlchemy、Alembic 和快照的关系。
5. [前端](./frontend)：理解前端只做展示和交互，不复制后端业务规则。
6. [客户端](./client)：理解 `wfm-agent` 和 `wfmctl` 的职责。
7. [实时事件](./events)：理解 SSE 事件边界和页面刷新方式。
8. [MQTT 协议](./mqtt-protocol)：理解服务端、EMQX 和客户端之间的控制通道。
9. [API 契约](./api-contract)：理解 API 响应、错误和下载 token。
10. [协作约定](./collaboration)：修改代码前先确认开发边界。

## 按任务查阅

| 你要做什么 | 先读 | 再对照 |
| --- | --- | --- |
| 新增一个控制台页面 | [前端](./frontend) | [后端](./backend)、[API 参考](/reference/api)、[实时事件参考](/reference/realtime) |
| 新增或调整后端接口 | [API 契约](./api-contract) | [后端](./backend)、[错误码](/reference/errors)、[MCP 参考](/reference/mcp) |
| 改数据库字段或表结构 | [数据库](./database) | [数据模型](/reference/data-model)、[快照参考](/reference/snapshot) |
| 改动态客户端控制逻辑 | [客户端](./client) | [MQTT 协议](./mqtt-protocol)、[MQTT 消息](/reference/mqtt-messages)、[客户端接入时序](/reference/client-lifecycle) |
| 改 Mesh 生成或 AllowedIPs | [后端](./backend) | [快速组网参考](/reference/quick-mesh)、[数据模型](/reference/data-model) |
| 改 WireGuard / AmneziaWG 参数 | [客户端](./client) | [协议参数](/reference/protocols)、[MQTT 消息](/reference/mqtt-messages) |
| 改 MCP 能力 | [API 契约](./api-contract) | [MCP 参考](/reference/mcp)、[安全边界](/reference/security) |
| 改部署或环境变量 | [总体架构](./architecture) | [环境变量](/reference/env)、[Docker 部署](/deploy/)、[反向代理](/deploy/reverse-proxy) |

## 修改代码前先确认

WG Free Mesh 的核心原则是：后端和数据库是业务真相来源，前端只是展示、输入和调用，客户端只执行本机动作。

涉及以下内容的变更必须同步文档：

- API 路径、请求字段、响应字段或错误码。
- 数据表结构、迁移脚本和快照内容。
- MQTT topic、payload、ACK 或在线状态规则。
- MCP resource、tool、权限和审计行为。
- Docker、环境变量、反向代理和部署目录。
- 客户端命令、安装方式和本地文件结构。
