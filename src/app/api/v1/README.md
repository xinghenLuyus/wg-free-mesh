# api/v1

`api/v1/` 是当前公开 API 版本。

## 约定

- `router.py` 汇总 v1 下的所有业务 router。
- `routers/` 下按业务域拆分文件。
- 修改路径、请求体、响应体或错误码时，同步更新 `docs/API契约原则.md` 和 `docs/后端设计.md`。

