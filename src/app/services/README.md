# services

`services/` 保存应用服务和用例编排。

## 当前内容

- `control_plane_service.py`：控制平面主服务，编排配置、端点、Mesh、同步、运行态、备份和系统状态。
- `config_service.py`：配置服务兼容入口，调用当前 SQLite store。
- `node_service.py`：端点服务兼容入口，使用当前节点模型。
- `mesh_service.py`：Mesh 服务兼容入口，使用当前 PeerLink 与 NodeType 模型。
- `realtime_service.py`：SSE 实时事件发布和订阅。

## 约定

- 服务层承接业务动作，前端不承担批量一致性逻辑。
- 标签创建、删除、批量应用和端点归属变更由后端服务完成。
- 旧模型名不得继续出现在服务层，例如 `NodeRole`、`NodeStatus`、`MeshLink`。
- 修改服务层后需要通过 `mypy app`。
