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
