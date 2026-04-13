# core

`core/` 保存跨业务的基础设施代码。

## 当前内容

- `config.py`：环境变量和应用配置。
- `responses.py`：统一响应 envelope。
- `errors.py`：应用异常和异常处理器。

## 约定

- 不放具体业务逻辑。
- 修改统一错误格式时，同步更新 API 文档。

