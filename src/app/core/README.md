# core

`core/` 保存跨业务的基础设施代码。

## 当前内容

- `config.py`
  - `Settings`：统一读取 `src/.env` 与环境变量，包含 API 前缀、token 有效期、开发测试开关与默认时区。
  - `get_settings()`：带缓存的配置实例获取函数。
- `responses.py`
  - `ApiResponse` / `ApiErrorResponse`：统一响应 envelope。
  - `ok(...)`：快速构造成功响应。
- `errors.py`
  - `AppError`：带错误码、状态码和细节的业务异常。
  - `install_exception_handlers(...)`：注册 FastAPI 全局异常处理。
- `security.py`
  - `generate_token_secret()`：生成 token secret。
  - `hash_password(...)` / `verify_password(...)`：密码哈希与校验。
  - `create_access_token(...)` / `decode_access_token(...)`：JWT 签发与解析。
- `validation.py`
  - `strip_required_text(...)` / `strip_optional_text(...)`：基础字符串清洗。
  - `normalize_string_list(...)`：字符串数组去空、去重与标准化。

## 约定

- 不放具体业务逻辑。
- 修改统一错误格式时，同步更新 API 文档。
