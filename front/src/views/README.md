# views

`views/` 保存页面级 Vue 组件。

## 当前页面

- `LoginView.vue`
- `HomeView.vue`
- `ConfigWorkspaceLayout.vue`
- `ConfigOverviewView.vue`
- `NodeWorkspaceLayout.vue`
- `NodesView.vue`
- `MeshView.vue`
- `ApplyView.vue`
- `EndpointsView.vue`
- `SettingsView.vue`
  - 控制台语言、主题模式、MQTT、密码和快照管理页面。
  - 快照卡片负责创建备注、修改备注、导入、导出、恢复和删除。
- `HelpView.vue`
- `SystemView.vue`

## 约定

- 页面组件作为组合层。
- 页面信息架构按“配置 -> 节点 -> 节点能力模板”组织。
- 配置列表只显示配置，不展开配置子页面。
- 节点页面保留公共节点头和返回配置按钮。
- “同步配置”默认表示系统态同步到同步态。
- 页面级弹窗需要保留说明区、分组表单、明确主按钮和危险区。
- 首页配置、概览节点、快照列表采用统一卡片语言，列表视图仍叫“列表”。
- 视觉细节优先复用 `src/assets/main.css` 的全局按钮、表单、弹窗和表格样式。
- 页面业务反馈统一调用 `src/utils/notify.ts`，以右上角弹窗展示。
- 配置概览页的标签管理只负责收集标签和端点选择，创建、删除、批量应用由后端标签接口完成。
- 节点页面右上角的端点设置负责编辑端点字段，所属标签通过后端标签接口单独保存。
- 节点公网地址必须拆分展示和编辑：`ipv4_address` 表示公网 IPv4 或域名，`ipv6_address` 表示公网 IPv6。
- Mesh 连接的自动 Endpoint 需要显式选择 IPv4 / IPv6 / domain 地址来源。
