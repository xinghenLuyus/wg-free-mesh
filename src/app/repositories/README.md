# repositories

`repositories/` 保存数据访问实现。

## 当前内容

- `sqlite.py`
  - `SQLiteStore`：对外兼容入口，只负责组合各个 SQLite mixin，并继续导出全局 `store`。
- `sqlite_common.py`
  - SQLite 仓储层公共 helper：数值/字符串归一化、AllowedIPs 校验、Endpoint payload 解析、标签归一化。
- `sqlite_client_state.py`
  - 客户端绑定、MQTT 心跳、客户端在线态、节点类型切换后的运行态清理。
  - `list_client_states(...)`：按配置批量拉取客户端状态，给运行态快照和配置概览复用，避免逐节点重复查询。
- `sqlite_config_mesh.py`
  - 配置、节点、标签、Mesh 连接组、节点依赖变更与 peer link 持久化。
  - `_list_configs_base(...)` / `_list_nodes_for_configs(...)` / `_list_peer_links_for_configs(...)`：给系统状态、配置列表等聚合场景提供批量取数入口。
  - `_topology_summaries_for_prefetched(...)`：在已预取 `config/nodes/peer_links` 的前提下批量生成拓扑摘要，减少重复拓扑重算。
  - 配置、节点、Mesh 的写方法只负责持久化和返回受影响对象；整配置重算改由服务层后台队列调度，不再在仓储写路径里同步阻塞。
- `sqlite_runtime.py`
- `sqlite_endpoint_helpers.py`
  - Mesh Endpoint 解析、keepalive 展示、拓扑校验代理、`.conf` 文件路径与落盘 helper。
  - `_write_service_conf_if_changed(...)`：仅在内容变化时才覆写 `.conf` 文件，减少无意义磁盘写入。
- `sqlite_runtime_state.py`
  - 运行态快照、端点控制日志、控制 ACK 回写、端点状态聚合。
  - `_list_runtime_rows(...)` / `_list_runtime_rows_for_configs(...)` / `_list_node_config_states(...)`：为系统状态、配置概览、节点工作区提供批量运行态和同步态读取。
  - 端点命令行回显日志按节点硬性保留最近 20 条，新日志入库后自动清理更老记录，防止表持续膨胀。
- `sqlite_sync_settings.py`
  - WireGuard 配置预览与同步、下载包、系统设置、密码、密钥生成、系统状态与配置概览聚合。
  - `_build_wg_preview_for_node(...)`：在单次预取上下文里复用节点和 Peer 数据，避免为每个 Peer 重复查节点。
  - `refresh_config_state(...)`：改为单次预取 `nodes/peer_links/runtime/state` 后批量更新，减少 N+1 查询与重复文件写入。
- `snapshot_repository.py`
  - `SnapshotRepository`：只负责 `backups` 表元数据读写，不再承担压缩包创建、恢复、导入导出。
  - `list_snapshots()` / `get_snapshot(...)`：读取快照元数据。
  - `upsert_snapshot(...)` / `replace_snapshots(...)`：同步磁盘快照索引到数据库。
  - `update_snapshot_note(...)` / `delete_snapshot(...)`：维护快照备注和元数据删除。
  - `normalize_allowed_ips(...)`：标准化并校验 AllowedIPs。
  - `delete_setting(...)` / `read_setting(...)` / `write_setting(...)`：系统设置存取。
- `naming.py`
  - `validate_config_name(...)`：校验配置名。
  - `config_artifact_name_segment(...)`：把文件名片段收敛成安全字符。
  - `node_config_artifact_stem(...)`：按 `配置名-节点名` 生成 `.conf` 文件 stem，并对非 ASCII 做百分号编码。
- `row_mappers.py`
  - `config_from_row(...)` / `node_from_row(...)` / `peer_link_from_row(...)`：数据库行映射。
  - `state_from_row(...)` / `runtime_from_row(...)` / `log_from_row(...)` / `snapshot_from_row(...)`：同步态、运行态、日志与快照映射。

## 约定

- 数据库模型确定后替换为 SQLAlchemy 仓储，并补充 Alembic migration。
- 优先按仓储职责拆模块，不把业务命名、Mesh 规则、WireGuard 配置生成等逻辑塞进通用 `util`。
- 拓扑校验、系统状态聚合、配置概览聚合、快照打包恢复和实时发布影响面不再继续膨胀进仓储层。
