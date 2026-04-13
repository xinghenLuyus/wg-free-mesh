# views

`views/` 保存页面级 Vue 组件。

## 当前页面

- `LoginView.vue`
- `HomeView.vue`
- `ConfigWorkspaceLayout.vue`
- `ConfigOverviewView.vue`
- `NodesView.vue`
- `MeshView.vue`
- `ApplyView.vue`
- `EndpointsView.vue`
- `SettingsView.vue`
- `HelpView.vue`
- `SystemView.vue`

## 约定

- 页面组件作为组合层。
- 页面信息架构优先对齐 `bak` 中已经验证过的布局。
- 配置内页面围绕同一份配置连续操作。
- 当页面出现多个独立 UI 区块或复杂状态时，拆分到 `components/` 或 `composables`。
