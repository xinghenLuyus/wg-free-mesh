# components

`components/` 保存可复用 Vue 组件。

## 当前内容

- `layout/AppLayout.vue`：后台主布局。

## 约定

- 组件使用明确的 props 和 emits。
- 复杂业务 UI 先抽成组件，再由页面组合。
- 不保留已经被页面结构淘汰的旧组件。
