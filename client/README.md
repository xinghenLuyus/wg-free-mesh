# client

`client/` 用于承载 `wfm` 客户端。

当前阶段先固化架构，不直接落代码。

## 当前方向

- 只做 `wfm-agent`
- 只做 `wfmctl`
- 不做主页面
- Windows 托盘只是后续可选附加项
- 绑定通过 `wfmctl + HTTPS 临时 token` 完成
- 运行期通信全部走 MQTT
- MQTT 凭据按节点隔离，topic ACL 按节点收口
- 配置下发和控制命令必须有 ACK，状态和日志是单向上报

## 设计原则

- 三个平台都要能无感知安装、开机启动、后台稳定运行
- 本地 profile 必须隔离
- MQTT 一次设计到位，不再把连接状态误当成真实运行状态
- 客户端主交互统一走命令行
- 不再使用注册文件、enrollment 文件和节点公私钥体系

## 参考文档

- [客户端设计](D:/wenjian/stepsave/project/wg-free-mesh/docs/客户端设计.md)
