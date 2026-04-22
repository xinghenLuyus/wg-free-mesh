# composables

`composables/` 保存页面和组件复用的前端状态逻辑。

## 当前内容

- `useRealtime.ts`
  - 统一管理全局 SSE 连接、重连、监听器分发和连接状态。
- `useConfigOverviewPrefs.ts`
  - 管理配置概览页的本地偏好，包括排序方式、标签筛选和网格/列表布局，并持久化到浏览器本地存储。

## 约定

- composable 只负责前端交互状态和副作用，不承载后端业务规则。
- 需要跨页面或跨刷新保留的前端轻量偏好，优先收进 composable，而不是直接散落在视图组件里。
