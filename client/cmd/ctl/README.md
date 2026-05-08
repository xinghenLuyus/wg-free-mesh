# wfmctl

`cmd/ctl` 编译为 `wfmctl`，是客户端唯一主交互入口。

当前已支持：

- `wfmctl bind --server <url> --token <token>`
- `wfmctl list`
- `wfmctl service install`
- `wfmctl service uninstall`
- `wfmctl service start`
- `wfmctl service stop`
- `wfmctl service restart`
- `wfmctl service status`

`bind` 写入机器级 profile 目录，因此生产环境需要管理员权限：

- Windows：管理员 PowerShell
- Linux/macOS：`sudo`

## 构建

```powershell
cd D:\wenjian\stepsave\project\wg-free-mesh\client
go build -o .\bin\wfmctl.exe .\cmd\ctl
```
