# api/v1

`api/v1/` 是当前公开 API 版本。

## 约定

- `router.py` 汇总 v1 下的所有业务 router。
- `__init__.py` 仅用于包初始化，不放业务逻辑。
- `deps.py` 保存 Bearer Token、下载 token 等依赖注入函数。
- `routing.py` 中的 `SessionProtectedAPIRouter` 用于给整组路由统一挂后台会话依赖。
- `routers/` 下按业务域拆分文件。
- Router 负责请求绑定和轻量协调；实时事件影响面通过 `events/PublishPlan` 收束，不在 Router 内手写散乱的 `publish_xxx()` 组合。
- 默认受后台会话保护的业务域优先使用 `routing.py` 中的 `SessionProtectedAPIRouter`，把鉴权收束在路由模块内部；只有下载等例外能力再单独声明专用 router。
- 修改路径、请求体、响应体或错误码时，同步更新 `docs/API契约原则.md` 和 `docs/后端设计.md`。
- `settings.py` 同时负责控制台界面偏好、MQTT 设置和密码修改，不把轻量偏好拆成独立业务域。

## 当前文件

- `deps.py`
  - `_extract_bearer_token(...)`：从请求头解析 Bearer Token。
  - `require_current_user(...)`：要求后台会话有效。
  - `optional_current_user(...)`：允许匿名读取当前会话状态。
  - `require_download_grant(...)`：校验下载专用 token 与当前配置/节点范围。
- `router.py`
  - 聚合 v1 全部业务 router。
- `routing.py`
  - `SessionProtectedAPIRouter`：给一组路由统一附加 `require_current_user` 依赖。
