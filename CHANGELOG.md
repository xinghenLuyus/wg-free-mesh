# Changelog / 更新日志

Notable changes are listed by version, newest first. English notes are followed by their Chinese equivalents.

按版本记录主要变化，最新版本在前。每个版本先列英文说明，再附对应中文说明。

## 1.0.0-rc.9 - 2026-10-20

### English

- Add client self-update from GitHub or the binding server, pinned to the server version with package verification and downgrade protection.
- Unify tunnel configuration replacement with three configuration generations, interrupted-operation records, and owned-interface recovery; improve macOS service handling and local interface naming.
- Add optional Linux hub forwarding rules to Quick Mesh and improve binding commands and endpoint name hints.

### 中文

- 新增客户端自更新，支持 GitHub 或绑定服务端来源，对齐服务端版本，并校验更新包、禁止降级。
- 统一隧道配置替换流程，保留三代配置、记录中断进度并恢复所属接口；完善 macOS 服务管理和本地接口名称处理。
- 快速组网新增可选的 Linux 中心节点转发规则，优化绑定命令及端点名称提示。

## 1.0.0-rc.8 - 2026-10-10

### English

- Fix Mesh pair edits swapping forward and reverse settings by matching each direction to its actual endpoints.
- Improve endpoint header layout and document directional Mesh updates.

### 中文

- 修复编辑 Mesh 对时正反向设置对调的问题，按实际端点匹配连接方向。
- 优化端点页头布局，完善 Mesh 方向更新说明。

## 1.0.0-rc.7 - 2026-10-08

### English

- Add AmneziaWG 1.5, 2.0, and 3.1 selection, configurable randomized traffic profiles, and per-endpoint parameter generation.
- Improve configuration QR codes, fullscreen scanning, and page navigation/loading transitions.
- Update pnpm and container build setup, and align English documentation with Chinese.

### 中文

- 支持切换 AmneziaWG 1.5、2.0、3.1，新增可配置的流量伪装随机策略和单端点参数生成。
- 优化配置二维码、全屏扫描及页面切换与加载体验。
- 更新 pnpm 和容器构建配置，对齐中英文文档。

## 1.0.0-rc.6 - 2026-09-17

### English

- Make MQTT-disabled mode consistently disable remote-control features and treat existing dynamic endpoints as static without deleting their stored data.
- Publish Docker images for both Linux amd64 and arm64, and expand bilingual reference documentation.

### 中文

- 完善 MQTT 关闭模式：禁用远程控制相关功能，将已有动态端点视为静态端点，保留其原有存储数据。
- Docker 镜像支持 Linux amd64 和 arm64，补充中英文参考文档。

## 1.0.0-rc.5 - 2026-09-16

### English

- Fix client toolchain switching when changing tunnel protocols, stopping the original tunnel before applying the target protocol.
- Add a concise Docker update guide with a snapshot backup reminder.

### 中文

- 修复切换隧道协议时的客户端工具链处理，应用目标协议前先停止原隧道。
- 新增简明 Docker 更新指南及快照备份提示。

## 1.0.0-rc.4 - 2026-05-29

### English

- Correct WireGuard public-key derivation to use X25519 and validate private-key length.

### 中文

- 修正 WireGuard 公钥派生，使用 X25519 并校验私钥长度。

## 1.0.0-rc.3 - 2026-05-29

### English

- Fix Linux/macOS tunnel shutdown and configuration replacement by passing the configuration file path to the quick tool.

### 中文

- 修复 Linux/macOS 隧道停止及配置替换，向 quick 工具传入实际配置文件路径。

## 1.0.0-rc.2 - 2026-05-29

### English

- Improve Windows agent and tunnel startup verification, timeout reporting, and service diagnostics.
- Expand the client download page and add local development and download reference guides.

### 中文

- 完善 Windows agent 和隧道启动确认、超时提示及服务诊断。
- 完善客户端下载页面，补充本地开发和下载参考指南。

## 1.0.0-rc.1 - 2026-05-28

### English

- Initial tagged release candidate with WireGuard/AmneziaWG configuration, Mesh networking, Quick Mesh, and MQTT-based client control.
- Include SQLite/PostgreSQL deployment, application snapshots, and MCP integration.
- Establish tag-triggered releases with container images and cross-platform client packages.

### 中文

- 首个带 tag 的候选版本，提供 WireGuard/AmneziaWG 配置管理、Mesh 网络、快速组网及基于 MQTT 的客户端控制。
- 提供 SQLite/PostgreSQL 部署、应用级快照和 MCP 接入。
- 建立由 tag 触发的发布流程，提供容器镜像和跨平台客户端包。

