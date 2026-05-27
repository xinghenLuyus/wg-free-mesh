# 参考索引

参考文档用于查阅稳定接口、协议字段、错误码和安全边界。这里不是教程，而是系统行为的事实手册。

## 访问与接口

- [认证与权限](./auth)：管理员会话、下载 token、MCP token 和来源限制。
- [API](./api)：REST、客户端绑定、内部 EMQX 回调和开发接口。
- [实时事件](./realtime)：SSE 事件流、事件格式和前端订阅方式。
- [MCP](./mcp)：MCP 资源、工具、写操作确认和审计。

## 协议与数据

- [MQTT 消息](./mqtt-messages)：客户端状态、控制命令、ACK 和 Topic 授权。
- [客户端接入时序](./client-lifecycle)：动态端点绑定、上线、掉线、重置和页面切换规则。
- [下载与文件 token](./downloads)：客户端产物、配置包、快照导出和短期下载 URL。
- [快照](./snapshot)：应用级快照内容、加密和恢复边界。
- [数据模型](./data-model)：配置、端点、Mesh 对、运行态和同步态。
- [协议参数](./protocols)：WireGuard、AmneziaWG 2.0 和 AWG 参数规则。
- [快速组网](./quick-mesh)：网关节点式、全连接和 Free Mesh 的生成规则。

## 运行边界

- [安全边界](./security)：公网来源、MCP、高风险能力和数据保护。
- [环境变量](./env)：部署环境变量。
- [错误码](./errors)：统一错误响应和常见业务错误。
