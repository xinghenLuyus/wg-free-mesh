# client

`client/` 用于承载 Go 版 `wfm` 客户端。

当前已经落地客户端核心通信与服务化骨架：

- `wfmctl bind` 通过 HTTPS 一次性 token 绑定动态节点。
- `wfmctl unbind` 移除本机绑定文件和本地凭据。
- `wfmctl install / uninstall / start / stop / restart` 管理系统级后台服务。
- `wfmctl` 不提供本地 profile 级控制；所有具体 WireGuard 控制动作都由服务端通过 MQTT 下发。
- `wfm-agent` 读取机器级 profile，连接 EMQX。
- `wfm-agent` 会发布 `heartbeat`，并上报 `client_online` / `wg_online`。
- `wfm-agent` 会订阅 `config/push`、`control`、`detect`、`info` 并返回对应 ACK。
- `info` 当前用于控制台主动请求 `wg show`；命令输出统一通过 `event` topic 回传。

## 当前方向

- 只做 `wfm-agent` 和 `wfmctl`
- 不做主页面
- 不做本地 IPC
- 不做本地 profile 级 `start/stop/restart/logs`
- Windows 托盘只是后续可选附加项
- 绑定通过 `wfmctl + HTTPS 临时 token` 完成
- 移除绑定通过 `wfmctl unbind <profile_id>` 完成，只影响本机文件
- `wfmctl install` 会把当前 `wfmctl` 所在目录加入全局命令路径，让后续可以直接执行 `wfmctl`
- 本地只维护系统级 `wfm-agent` 服务，服务启动时统一加载所有 profile
- 运行期通信全部走 MQTT
- MQTT 凭据按节点隔离，topic ACL 按节点收口
- 配置下发、控制命令、主动探测和诊断信息必须有 ACK
- ACK 只表示命令执行状态；命令行输出统一通过 `event` 回传
- 动态节点先经过客户端初始化页，再进入真正控制页
- 绑定命令为一次性命令，默认 5 分钟有效
- heartbeat 每 30 分钟上报一次，45 分钟未收到由服务端判定离线
- 前端存在 SSE 订阅时，服务端每 2 分钟主动发送 `detect`
- 客户端应以系统服务运行，否则 WireGuard 状态读取和控制可能权限不足

## 使用方式

### 1. 构建客户端

```powershell
cd D:\wenjian\stepsave\project\wg-free-mesh\client
go build -o .\bin\wfmctl.exe .\cmd\ctl
go build -o .\bin\wfm-agent.exe .\cmd\agent
```

### 2. 绑定节点

绑定 token 不应手写，应该在控制台动态节点的“端点控制”初始化页点击“生成节点绑定命令并复制”获得。

Windows 生产环境建议使用管理员 PowerShell：

```powershell
.\bin\wfmctl.exe bind --server https://example.com --token <token>
```

Linux / macOS 生产环境建议使用 `sudo`：

```bash
sudo ./wfmctl bind --server https://example.com --token <token>
```

`bind` 会写入机器级 profile 目录：

- Windows：`C:\ProgramData\wg-free-mesh\profiles`
- Linux：`/etc/wg-free-mesh/profiles`
- macOS：`/Library/Application Support/WG Free Mesh/profiles`

移除本机绑定：

Windows 生产环境建议继续使用管理员 PowerShell。Linux / macOS 生产环境建议使用 `sudo`。

```powershell
wfmctl unbind <profile_id>
wfmctl unbind --all
```

`unbind` 删除本机 profile、MQTT 凭据、目标配置和运行文件，不负责撤销服务端节点权限。服务端侧权限回收仍应在控制台执行“重置客户端”、节点转静态、节点删除或配置停用。

如果 `wfm-agent` 服务正在运行，`unbind` 需要重启整个服务，让已加载的 MQTT session 立即退出并重新扫描剩余 profile。

### 3. 安装并启动客户端

`install` 在三端语义一致：安装系统服务、设置开机自启、立即启动服务，并把当前 `wfmctl` 所在目录加入全局命令路径。`start` 仍然保留，用于服务已安装但当前未运行时手动启动。

如果安装后移动了 `wfmctl` 所在目录，全局命令路径会失效。此时在新目录重新执行 `wfmctl install` 即可修复。

Windows：

```powershell
.\bin\wfmctl.exe install
wfmctl status
```

Linux：

```bash
sudo ./wfmctl install
wfmctl status
```

macOS：

```bash
sudo ./wfmctl install
wfmctl status
```

服务运行账号：

- Windows：`LocalSystem`
- Linux：`root`
- macOS：`root`

### 4. 常用维护命令

```powershell
wfmctl list
wfmctl unbind <profile_id>
wfmctl status
wfmctl logs
wfmctl logs --lines 200
wfmctl start
wfmctl stop
wfmctl restart
wfmctl version
wfmctl --version
wfmctl -v
wfmctl uninstall
wfmctl uninstall --purge
```

命令语义：

- `wfmctl list`：列出本机已绑定 profile。
- `wfmctl unbind <profile_id>`：移除本机某个绑定，并在服务运行时重启系统服务使变更生效。
- `wfmctl unbind --all`：移除本机全部绑定；这是高风险操作，必须显式传入 `--all`。
- `wfmctl status`：展示本机服务状态、profile 数量和绑定文件完整性。
- `wfmctl logs`：查看系统服务日志。
- `wfmctl start`：启动已安装服务。
- `wfmctl stop`：停止系统服务，但保留服务定义、开机自启、profile 和日志。
- `wfmctl restart`：重启系统服务，让 agent 重新扫描本机 profile。
- `wfmctl version` / `wfmctl --version` / `wfmctl -v`：显示客户端版本。
- `wfmctl uninstall`：停止服务、取消开机自启、删除服务定义并移除全局命令路径，不删除本机 profile。
- `wfmctl uninstall --purge`：在 `uninstall` 基础上删除本机 profile、runtime 和日志目录。

本地不提供单个 profile 的启动、停止、重启或日志命令。`unbind` 只是删除本机绑定文件，不是运行控制。要控制 WireGuard 启停、下发配置、查看 `wg show`，应在服务端控制台操作，由服务端通过 MQTT 向 `wfm-agent` 下发命令。

### 5. 本地调试

开发调试可以直接运行 agent，但该方式通常没有足够权限读取或控制 WireGuard：

```powershell
go run .\cmd\agent
```

生产节点应使用系统服务运行。

## 手动构建

```powershell
cd D:\wenjian\stepsave\project\wg-free-mesh\client
go build ./...
```

常用命令：

```powershell
go build -o .\bin\wfmctl.exe .\cmd\ctl
go build -o .\bin\wfm-agent.exe .\cmd\agent
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

## 设计原则

- 三个平台都要能无感知安装、开机启动、后台稳定运行
- 三端用户命令语义保持一致：`install` 即安装、自启、启动并配置全局命令路径
- 本地 profile 必须隔离
- MQTT 一次设计到位，不再把连接状态误当成真实运行状态
- 客户端主交互统一走 `wfmctl`
- `wfmctl` 只做本地绑定、状态查看和系统服务维护
- 本机绑定可以移除，但服务端权限回收必须由服务端控制台完成
- 具体业务控制统一从服务端发起
- 不再使用注册文件、enrollment 文件和节点公私钥体系

## 参考文档

- [客户端设计](D:/wenjian/stepsave/project/wg-free-mesh/docs/客户端设计.md)
