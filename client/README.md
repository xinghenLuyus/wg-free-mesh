# client

`client/` 用于承载 Go 版 `wfm` 客户端。

当前已经落地最小 MQTT 通信闭环：

- `wfmctl bind` 通过 HTTPS 一次性 token 绑定动态节点。
- `wfm-agent` 读取本地 profile，连接 EMQX。
- `wfm-agent` 会发布 `event` 和 `heartbeat`。
- `wfm-agent` 会订阅 `config/push`、`control`、`detect` 并返回对应 ACK。
- 当前阶段不执行真实 WireGuard 控制，只验证 MQTT 双向通信链路。

## 当前方向

- 只做 `wfm-agent`
- 只做 `wfmctl`
- 不做主页面
- Windows 托盘只是后续可选附加项
- 绑定通过 `wfmctl + HTTPS 临时 token` 完成
- 运行期通信全部走 MQTT
- MQTT 凭据按节点隔离，topic ACL 按节点收口
- 配置下发和控制命令必须有 ACK，状态和日志是单向上报
- 动态节点先经过客户端初始化页，再进入真正控制页
- 绑定命令为一次性命令，默认 5 分钟有效
- 客户端状态对控制台只保留：在线 / 掉线 / 离线

## 手动构建

```powershell
cd D:\wenjian\stepsave\project\wg-free-mesh\client
go build ./...
```

常用命令：

```powershell
go build -o .\bin\wfmctl.exe .\cmd\ctl
go build -o .\bin\wfm-agent.exe .\cmd\agent
go run .\cmd\ctl bind --server http://127.0.0.1:8000 --token <token>
go run .\cmd\ctl list
go run .\cmd\agent
```

如果只想更新单个二进制：

```powershell
cd D:\wenjian\stepsave\project\wg-free-mesh\client
go build -o .\bin\wfmctl.exe .\cmd\ctl
go build -o .\bin\wfm-agent.exe .\cmd\agent
```

如果需要为 Linux 或 macOS 交叉构建，可临时指定目标平台：

```powershell
$env:GOOS='linux'; $env:GOARCH='amd64'; go build -o .\bin\wfm-agent-linux-amd64 .\cmd\agent
$env:GOOS='linux'; $env:GOARCH='amd64'; go build -o .\bin\wfmctl-linux-amd64 .\cmd\ctl
Remove-Item Env:GOOS
Remove-Item Env:GOARCH
```

绑定 token 不应手写，应该在控制台动态节点的“端点控制”初始化页点击“生成节点绑定命令并复制”获得。

## 设计原则

- 三个平台都要能无感知安装、开机启动、后台稳定运行
- 本地 profile 必须隔离
- MQTT 一次设计到位，不再把连接状态误当成真实运行状态
- 客户端主交互统一走命令行
- 不再使用注册文件、enrollment 文件和节点公私钥体系

## 参考文档

- [客户端设计](D:/wenjian/stepsave/project/wg-free-mesh/docs/客户端设计.md)
