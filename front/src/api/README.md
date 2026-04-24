# api

`front/src/api/` 是前端唯一的后端调用出口。

## 当前内容

- `client.ts`
  - Axios 实例
  - 统一错误归一化
  - 通用请求封装
- `base.ts`
  - 统一计算前端当前应直连的后端地址
  - 开发态在 `5173` 时默认改连同主机 `8000`
  - `VITE_API_BASE_URL` 可覆盖默认后端地址
- `modules.ts`
  - 配置、节点、Mesh、同步状态、端点控制、设置、备份、系统状态 API
  - 备份域已包含快照创建、备注修改、导入、导出、恢复和删除
  - 设置域中的 MQTT 接口只承载客户端可见的 `host / port / tls`

## 约定

- 页面组件不直接拼 URL
- 新增接口时，先更新 `docs/API接口设计.md`
- SSE 实时消息不混进普通 HTTP 请求封装，单独由 composable 处理
- 开发态不再依赖 Vite 代理；HTTP 和 SSE 都直接访问后端
