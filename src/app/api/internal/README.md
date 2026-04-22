# internal

`src/app/api/internal/` 保存仅供内部基础设施调用的 HTTP 接口。

## 当前边界

- 不对浏览器和普通客户端公开
- 只承接容器内 broker、网关或其它内部组件的回查请求
- 当前主要用于 EMQX HTTP Authorization

## 当前模块

- `router.py`：聚合内部接口路由。
- `routers/README.md`：内部路由目录说明。
- `routers/emqx.py`：EMQX HTTP AuthZ 回查入口。
