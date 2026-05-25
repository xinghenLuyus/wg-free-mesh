# tests

`tests/` 保存后端自动化测试。

## 当前内容

- `conftest.py`：隔离测试环境，使用内存 SQLite，关闭 MQTT 后台服务，并提供认证客户端夹具。
- `test_health.py`：健康检查接口测试。
- `test_mcp_access.py`：MCP Token 生命周期和调用审计测试。
- `test_auth.py`：初始化、登录、鉴权和开发重置接口测试。
- `test_configs_and_nodes.py`：配置、节点、同步状态和鉴权错误测试。
- `test_settings.py`：UI 设置与客户端 MQTT 接入地址重置测试。
- `test_snapshots.py`：应用级快照创建、导出和恢复测试。
- `test_data_layer.py`：数据库初始化与默认设置测试。

## 约定

- 新增业务规则时优先补领域服务测试。
- 新增 API 行为时补接口测试。
- 涉及数据库的测试必须走夹具隔离，不能依赖本机 `src/data`。
