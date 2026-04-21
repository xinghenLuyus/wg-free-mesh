# v0 开发测试接口

`/api/v0` 仅保留开发和联调阶段使用的测试接口，不参与正式业务 API 契约。

当前提供：

- `POST /api/v0/dev/reset-bootstrap`
  - 用途：清空管理员密码、登录 token secret、界面语言和界面主题偏好
  - 结果：系统重新回到 setup 初始化流程
  - 范围：不删除配置、节点、Mesh 关系和其它业务数据

该分组默认只在开发模式开启，禁止前端业务依赖。

## 当前文件

- `router.py`
  - 聚合 `/api/v0` 下所有开发测试 router。

## 子目录

- [routers/README.md](D:/wenjian/stepsave/project/wg-free-mesh/src/app/api/v0/routers/README.md)
