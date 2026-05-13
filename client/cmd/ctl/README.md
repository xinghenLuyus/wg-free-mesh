# wfmctl

`cmd/ctl` 编译为 `wfmctl`，是客户端唯一主交互入口。

当前已支持：

- `wfmctl install`
- `wfmctl uninstall`
- `wfmctl uninstall --purge`
- `wfmctl bind --server <url> --token <token>`
- `wfmctl unbind <profile_id>`
- `wfmctl unbind --all`
- `wfmctl list`
- `wfmctl status`
- `wfmctl logs`
- `wfmctl logs --lines <n>`
- `wfmctl start`
- `wfmctl stop`
- `wfmctl restart`
- `wfmctl version`
- `wfmctl --version`
- `wfmctl -v`
- `wfmctl help [command]`

`wfmctl` 是唯一用户入口，`wfm-agent` 是后台服务实现细节。旧的 `wfmctl service ...` 入口不再使用。

`install` 安装系统服务、设置开机自启、立即启动服务，并把当前 `wfmctl` 所在目录加入全局命令路径。`uninstall` 默认只移除服务和全局命令路径，不删除 profile、runtime 和日志；需要彻底清理时显式使用 `wfmctl uninstall --purge`。

`bind` / `unbind` 会写入或删除机器级 profile 目录；如果后台服务正在运行，会自动重启服务让 profile 变更立即生效。因此生产环境建议使用管理员权限：

- Windows：管理员 PowerShell
- Linux/macOS：`sudo`

## 构建

正式发布请在 `client/` 根目录使用统一脚本，它会从 `src/pyproject.toml` 读取版本并注入二进制：

```powershell
cd D:\wenjian\stepsave\project\wg-free-mesh\client
python build_release.py --target windows/amd64
```

下面的命令只用于开发调试，版本显示为 `dev`：

```powershell
cd D:\wenjian\stepsave\project\wg-free-mesh\client
go build -o .\bin\wfmctl.exe .\cmd\ctl
```
