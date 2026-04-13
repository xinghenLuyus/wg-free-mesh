# api

`front/src/api/` 是前端唯一的后端调用出口。

## 当前内容

- `client.ts`
  - Axios 实例
  - 统一错误归一化
  - 通用请求封装
- `modules.ts`
  - 配置、节点、Mesh、同步状态、端点控制、设置、备份、系统状态 API

## 约定

- 页面组件不直接拼 URL
- 新增接口时，先更新 `docs/API接口设计.md`
- WebSocket 实时消息不混进普通 HTTP 请求封装，单独由 composable 处理
