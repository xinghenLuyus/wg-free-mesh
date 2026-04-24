# wfmctl

`cmd/ctl` 编译为 `wfmctl`，是客户端唯一主交互入口。

当前已支持：

- `wfmctl bind --server <url> --token <token>`
- `wfmctl list`

## 构建

```powershell
cd D:\wenjian\stepsave\project\wg-free-mesh\client
go build -o .\bin\wfmctl.exe .\cmd\ctl
```
