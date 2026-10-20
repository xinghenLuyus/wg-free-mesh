# client

`client/` 用于承载 Go 版 `wfm` 客户端。

当前已经落地客户端核心通信与服务化骨架：

- `wfmctl bind` 通过 HTTPS 一次性 token 绑定动态节点。
- `wfmctl unbind` 移除本机绑定文件和本地凭据。
- `wfmctl install / uninstall / start / stop / restart` 管理系统级后台服务。
- `wfmctl` 不提供本地 profile 级控制；所有具体 WireGuard / AmneziaWG 控制动作都由服务端通过 MQTT 下发。
- `wfm-agent` 读取机器级 profile，连接 EMQX。
- `wfm-agent` 会发布 `heartbeat`，并上报 `client_online` / `wg_online`。
- `wfm-agent` 会订阅 `config/push`、`control`、`detect`、`info` 并返回对应 ACK。
- `wfmctl update [--server] [编号或 Profile ID]` 将本机两程序升级到指定绑定的服务端版本；默认绑定编号 1、默认 GitHub，`--server` 使用服务端编译。相同版本跳过、低版本拒绝；不改 MQTT 和数据库结构。编号与 `list` 的目录排序一致。
- 更新需要安装好的服务及 root/管理员权限；独立助手处理自身替换，结果在系统数据目录的 `update/active/result.log` 和 `state.json`。未完成事务阻止重复覆盖；仅在激活前允许撤销未完成替换，不自动降级已激活程序。用户态隧道可能随服务停止短暂中断，按记录恢复。
- 发布包包含 `package.json`（版本、平台、两程序 SHA-256），发布脚本输出 `.zip.sha256` 并上传 Release；更新客户端拒绝缺少校验资料的包。版本从 Go 构建元信息读取，不通过执行旧 agent 的未知参数探测版本。
- `info` 当前用于控制台主动请求诊断输出；客户端根据服务端 payload 中的 `tunnel_protocol` 执行裸 `wg` 或 `awg`，命令输出统一通过 `event` topic 回传。

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
- MQTT TLS 开启时，绑定响应会保存服务端下发的 CA，客户端连接时会校验 CA 和 MQTT 主机名
- 配置下发、控制命令、主动探测和诊断信息必须有 ACK
- ACK 只表示命令执行状态；命令行输出统一通过 `event` 回传
- 动态节点先经过客户端初始化页，再进入真正控制页
- 绑定命令为一次性命令，默认 5 分钟有效
- heartbeat 每 30 分钟上报一次；服务端同时使用 heartbeat、ACK 和非离线 event 投影在线态
- 前端存在 SSE 订阅时，服务端每 2 分钟主动发送 `detect`
- `detect/ack` 会携带当前客户端版本，服务端据此刷新控制面板中的客户端版本字段。
- 客户端应以系统服务运行，否则 WireGuard 状态读取和控制可能权限不足
- MQTT topic、下发字段和 ACK 结构保持不变。配置包的 `manifest.json` 保存该代配置的协议、AWG 版本、具体工具链、名称、公钥和哈希；启停使用对应配置包，而不是用最新消息推测旧隧道的工具链。Linux/macOS 使用 `wg-quick` / `awg-quick`，Windows 使用 `wireguard.exe` / `amneziawg.exe` 的 tunnel service 命令；状态检查使用 `wg` / `awg`。
- 服务端会保存 bind 时生成的客户端 MQTT 密码，用于快照恢复后重建 EMQX 节点用户。恢复完成后客户端可能经历一次 MQTT 重连，重新连接成功后继续发送在线事件和心跳。

## 使用方式

### 1. 构建客户端

```powershell
cd path\to\wg-free-mesh\client
python build_release.py
```

发布构建会读取 [src/pyproject.toml](../src/pyproject.toml) 中的 `[project].version`，并通过 Go `ldflags` 注入 `wfmctl` / `wfm-agent`。构建产物输出到 `client/dist/`。Windows 发布目标额外包含 32 位 `windows/386`，Linux 与 macOS 仍只发布 64 位目标。

只构建单个平台：

```powershell
python build_release.py --target windows/amd64
```

### 2. 安装并启动客户端

`install` 在三端语义一致：安装系统服务、设置开机自启、立即启动服务，并把当前 `wfmctl` 所在目录加入全局命令路径。安装成功后会输出客户端终端标识，并执行 `wg -v`、`awg -v` 检查；检查结果只用于提示，不阻断安装流程。若缺少 WireGuard 或 AmneziaWG 工具链，按提示到服务端下载页面下载对应内核或工具链。`start` 仍然保留，用于服务已安装但当前未运行时手动启动。Linux 安装还会尝试写入项目自有 sysctl 配置并启用 IPv4 forwarding；macOS 安装会尝试启用 IPv4 forwarding，供受管端口转发生命周期命令使用。两端 forwarding 启用失败时只输出一行错误，不中断安装流程。

如果安装后移动了 `wfmctl` 所在目录，全局命令路径会失效。此时在新目录重新执行安装命令即可修复。

Windows 生产环境建议在解压后的客户端目录使用管理员 PowerShell：

```powershell
.\wfmctl.exe install; $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine")
wfmctl status
```

Linux 生产环境建议在解压后的客户端目录使用 `sudo`：

```bash
chmod +x ./wfmctl ./wfm-agent && sudo ./wfmctl install
wfmctl status
```

macOS 生产环境建议在解压后的客户端目录使用 `sudo`：

```bash
chmod +x ./wfmctl ./wfm-agent && sudo ./wfmctl install
wfmctl status
```

macOS 已加载的服务通过 `launchctl kickstart -k` 重启；未加载时才执行 `bootstrap`，失败保留原始错误。停止和重新安装会等待旧服务卸载完成（最多 10 秒）。安装的 launchd 环境包含 Apple Silicon 和 Intel Homebrew 工具路径。

服务运行账号：

- Windows：`LocalSystem`
- Linux：`root`
- macOS：`root`

### 3. 绑定节点

三端在发送绑定请求前统一检查管理员/root 权限、系统服务安装状态和 profile 目录写入能力；预检查失败不会消耗服务端 token。实际保存时仍会检查并返回写入错误。

绑定 token 不应手写，应该在控制台动态节点的“端点控制”初始化页点击“生成端点绑定命令并复制”获得。完成 `install` 后，三端都使用统一绑定命令：

```powershell
wfmctl bind --server https://example.com --token <token>
```

`bind` 会写入机器级 profile 目录：

- Windows：`C:\ProgramData\wg-free-mesh\profiles`
- Linux：`/etc/wg-free-mesh/profiles`
- macOS：`/Library/Application Support/WG Free Mesh/profiles`

`profile.json` 的 `interface_names` 保存服务端原始名称到本地接口名的映射；超出 15 字符时，使用绑定配置名编码后的前 12 字符。配置更新先按旧映射停止接口，再保存并使用新映射，同机绑定重名时报错。无映射的 profile 在读取时保留原接口名。

每个绑定目录以 `config/`、`config.old/`、`config.old2/` 保存当前及两代历史配置包，各包含具名 `.conf` 和 `manifest.json`。下发先准备、校验新包，再停止并确认本绑定的旧接口退出，然后轮换并按原运行状态恢复。`transition.json` 记录中断恢复进度；启动失败保留现场、返回失败，不自动回滚或反复执行生命周期命令。启动和停止同样检查本绑定的历史残留，归属不明、查询失败或停止超时均报错，不清理其它 VPN。

旧目录自动复制为配置包，保留原文件供旧接口停止和恢复使用，迁移本身不重启隧道；不支持降级。macOS 通过配置名称映射查询实际 `utun`，并校验公钥；运行接口丢失名称映射时保留现场并报错。配置正文包含接口名称注释，使仅改名也能进入现有哈希同步流程。

移除本机绑定：

Windows 生产环境建议继续使用管理员 PowerShell。Linux / macOS 生产环境建议使用 `sudo`。

```powershell
wfmctl unbind <profile_id>
wfmctl unbind --all
```

`unbind` 删除本机 profile、MQTT 凭据、目标配置和运行文件，不负责撤销服务端节点权限。服务端侧权限回收仍应在控制台执行“重置客户端”、节点转静态、节点删除或配置停用。

如果 `wfm-agent` 服务正在运行，`unbind` 需要重启整个服务，让已加载的 MQTT session 立即退出并重新扫描剩余 profile。

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
wfmctl update
wfmctl update --server
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
- `wfmctl update [--server] [编号或 Profile ID]`：以选定服务端版本升级两程序；默认编号 1，`--server` 使用服务端编译，否则使用 GitHub。结果查看命令打印的日志路径。
- `wfmctl version` / `wfmctl --version` / `wfmctl -v`：显示客户端版本。
- `wfmctl uninstall`：停止服务、取消开机自启、删除服务定义并移除全局命令路径，不删除本机 profile。
- `wfmctl uninstall --purge`：在 `uninstall` 基础上删除本机 profile、runtime 和日志目录。

本地不提供单个 profile 的启动、停止、重启或日志命令。`unbind` 只是删除本机绑定文件，不是运行控制。要控制 WireGuard 启停、下发配置、查看 `wg` / `awg` 诊断信息，应在服务端控制台操作，由服务端通过 MQTT 向 `wfm-agent` 下发命令。

### 5. 本地调试

开发调试可以直接运行 agent，但该方式通常没有足够权限读取或控制 WireGuard：

```powershell
go run .\cmd\agent
```

生产节点应使用系统服务运行。

## 手动构建

手动 `go build` 仅用于开发调试，二进制版本会显示为 `dev`。正式发布包必须使用 `python build_release.py` 或后端客户端下载页构建。

```powershell
cd path\to\wg-free-mesh\client
go build ./...
```

常用命令：

```powershell
go build -o .\bin\wfmctl.exe .\cmd\ctl
go build -o .\bin\wfm-agent.exe .\cmd\agent
go run ./cmd/ctl version
go run ./cmd/agent
```

如果只想更新单个二进制：

```powershell
cd path\to\wg-free-mesh\client
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

## 版本来源

项目唯一版本源是 [src/pyproject.toml](../src/pyproject.toml) 的 `[project].version`。

- 后端 API 版本展示读取该字段。
- 后端客户端下载构建读取该字段，并注入客户端二进制。
- `client/build_release.py` 读取该字段，并生成所有发布 zip。
- `client/internal/bind.Version` 默认值仅为开发占位 `dev`，不是版本源。

## 设计原则

- 三个平台都要能无感知安装、开机启动、后台稳定运行
- 三端用户命令语义保持一致：`install` 即安装、自启、启动并配置全局命令路径
- 本地 profile 必须隔离
- MQTT 一次设计到位，不再把连接状态误当成真实运行状态
- 客户端主交互统一走 `wfmctl`
- `wfmctl` 只做本地绑定、状态查看和系统服务维护
- 本机绑定可以移除，但服务端权限回收必须由服务端控制台完成
- 具体业务控制统一从服务端发起
- 不再使用注册文件和节点公私钥体系

## 参考文档

- [客户端设计](../docs/developer/client.md)
