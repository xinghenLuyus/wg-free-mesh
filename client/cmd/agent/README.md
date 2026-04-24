# wfm-agent

`cmd/agent` 编译为 `wfm-agent`，负责读取本地 profile 并为每个动态节点建立 MQTT 会话。

当前阶段只打通 MQTT 通信底座，不执行真实 WireGuard 控制。

## 构建

```powershell
cd D:\wenjian\stepsave\project\wg-free-mesh\client
go build -o .\bin\wfm-agent.exe .\cmd\agent
```
