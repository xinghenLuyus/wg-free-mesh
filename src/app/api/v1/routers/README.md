# routers

`routers/` 保存 v1 业务路由。

## 当前模块

- `auth.py`
  - `state(...)`：返回 setup 状态和当前认证状态。
  - `setup(...)`：首次初始化管理员密码并签发后台 token。
  - `login(...)`：登录并签发后台 token。
  - `session(...)`：校验当前后台 token。
  - `logout()`：返回前端可直接处理的退出结果。
  - `change_password(...)`：修改密码并轮换后台 token。
- `backups.py`
  - `list_snapshots()`：读取快照列表。
  - `download_snapshot(...)`：下载快照压缩包。
- `configs.py`
  - `list_configs()`：配置列表。
  - `get_config(...)`：单个配置详情。
  - `config_overview(...)`：配置概览页所需聚合数据。
- `endpoints.py`
  - `sync_status_for_config(...)` / `sync_status_for_node(...)`：同步状态。
  - `read_applied_conf(...)` / `download_package(...)`：同步态读取与下载材料。
  - `create_download_token(...)` / `download_conf(...)`：下载专用 token 与最终 `.conf` 下载。
  - `runtime_snapshot(...)` / `endpoint_status(...)` / `endpoint_logs(...)`：运行态与控制日志。
- `mesh.py`
  - `list_peer_links(...)`：配置下链路列表。
  - `mesh_workspace(...)`：节点 Mesh 工作区。
  - `peer_link_draft(...)`：新建连接草稿。
  - `generate_preshared_key()`：生成 PSK。
  - `validate_mesh(...)`：Mesh 校验。
  - `wg_preview(...)`：WireGuard 配置预览。
- `nodes.py`
  - `list_nodes(...)` / `get_node(...)`：节点列表与详情。
  - `list_tags(...)`：标签列表。
  - `suggest_ip(...)` / `validate_ip(...)`：虚拟 IP 建议与校验。
  - `generate_keys()` / `derive_public(...)`：WireGuard 密钥生成与公钥推导。
- `settings.py`
  - `_ui_settings_payload()`：读取界面偏好规范化结果。
  - `ui_settings()` / `update_ui_settings(...)`：界面语言和主题模式。
  - `mqtt_settings()` / `test_mqtt(...)`：MQTT 设置读取与测试。
  - `update_password(...)`：设置页修改密码。
- `system.py`
  - `_sse_frame(...)`：SSE 事件帧编码。
  - `health()`：健康检查。
  - `system_status(...)`：控制台系统状态聚合。
