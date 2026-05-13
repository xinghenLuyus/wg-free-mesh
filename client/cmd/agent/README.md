# wfm-agent

`cmd/agent` 编译为 `wfm-agent`，负责读取本地 profile 并为每个动态节点建立 MQTT 会话。

当前阶段已打通 MQTT 通信底座、heartbeat/detect/info 回传和 `wg show` 诊断输出。

生产节点应通过系统服务运行：

- Windows：`WfmAgent` Windows Service，账号 `LocalSystem`
- Linux：`wfm-agent.service` systemd service，账号 `root`
- macOS：`mesh.wg-free.wfm-agent` LaunchDaemon，账号 `root`

## 构建

正式发布请在 `client/` 根目录使用统一脚本，它会从 `src/pyproject.toml` 读取版本并注入二进制：

```powershell
cd D:\wenjian\stepsave\project\wg-free-mesh\client
python build_release.py --target windows/amd64
```

下面的命令只用于开发调试，版本显示为 `dev`：

```powershell
cd D:\wenjian\stepsave\project\wg-free-mesh\client
go build -o .\bin\wfm-agent.exe .\cmd\agent
```
