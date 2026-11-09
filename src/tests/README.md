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

## 运行观测验证

`test_runtime_observations.py` 覆盖端点三态、Mesh 双态、静态不适用、请求去重、快照精度、查看登记与隔离 API/数据库采集回环。`test_awg_migrations.py` 同时检查历史结构升级到当前观测结构。

Python 验证使用 `conda run -n wfm python -B -m pytest`。MQTT 采集测试使用替身，不连接实际 broker，不使用业务运行数据库。Go 的解析和安全参数测试位于 `client/internal/mqtt/observation_test.go`。
