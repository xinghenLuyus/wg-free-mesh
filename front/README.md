# front

`front/` 是本项目的 Vue 前端工程。

## 技术栈

- Vue 3
- Vite
- TypeScript
- Pinia
- Vue Router
- Element Plus

## 页面结构

当前前端按“配置 -> 节点 -> 节点能力模板”组织：

- 首次使用进入 `/setup` 设置 `admin` 管理员密码
- 登录页只负责登录，登录成功后保存服务端下发的 Bearer Token
- 左侧主导航：首页 / 设置 / 帮助 / 配置列表 / 退出登录 / 系统状态
- 配置列表只显示配置名称，不展开子页面
- 配置概览页负责配置头和节点工作区
- 配置设置通过配置头右侧“设置”进入，删除配置放在设置弹窗内
- 节点卡片点击进入节点页面
- 节点列表视图仍叫“列表”，视觉使用横向长条卡片，不使用传统表格标题行
- 节点页面包含公共节点头和三个模板：Mesh 网络 / 配置应用 / 端点控制
- 标签管理支持创建标签、删除标签、选择端点批量添加标签、从端点移除标签
- 节点页面右上角提供端点设置，用于编辑端点信息和所属标签
- 节点公网地址分为公网 IPv4 和公网 IPv6，不合并为单个公网端点
- 公网 IPv4 和公网 IPv6 都可以填写 IP 或域名
- Mesh 自动 Endpoint 只选择 IPv4 或 IPv6 公网入口；对应入口不存在时自动留空

## 界面约定

- 视觉方向是精致工具型控制台，保留当前业务布局，不擅自改变页面信息结构
- Element Plus 是唯一 UI 框架，结构性图标使用 `@element-plus/icons-vue`
- 全局按钮、输入框、弹窗、表格、卡片在 `src/assets/main.css` 中统一基础质感
- 配置、节点、快照等重复项目使用卡片或长条卡片，不用传统标题行列表承载主业务入口
- 弹窗表单需要有说明区、明确按钮层级和危险操作分区
- 全局通知和业务反馈统一通过 `src/utils/notify.ts` 触发右上角弹窗
- 通知关闭按钮外框带环形进度，悬停通知时暂停进度和自动关闭
- 页面代码不要直接使用 `ElMessage`，确认类交互仍可使用 `ElMessageBox`
- 标签是配置级后端资源，前端通过标签接口创建、删除、批量应用和维护端点归属
- 前端不得直接展示 `dynamic`、`static`、`auto`、`none`、`manual` 等英文枚举值，必须映射为中文

## 认证约定

- `src/stores/auth.ts` 是前端登录态唯一来源。
- `src/api/client.ts` 负责给后端请求统一附带 `Authorization: Bearer <token>`。
- `src/router/index.ts` 负责 `/setup`、`/login` 和业务页面的三态分流。
- token 保存在 `localStorage`，刷新后通过 `/api/v1/auth/state` 重新校验。
- 业务请求收到 `401` 会清理 token 并跳转登录页。
- 收到 `AUTH_SETUP_REQUIRED` 会跳转初始化页。
- WebSocket 连接需要把 token 放到查询参数中。

## 同步语义

- “同步配置”默认表示系统态同步到同步态
- “下发配置”表示同步态到客户端下发态
- 配置应用模板只展示系统态和同步态

## 路由约定

- `/` 为首页
- `/configs/:configId` 为配置概览
- `/configs/:configId/nodes/:nodeId` 为节点页，默认进入 Mesh 网络
- `/configs/:configId/nodes/:nodeId/mesh` 为节点 Mesh 网络
- `/configs/:configId/nodes/:nodeId/apply` 为节点配置应用
- `/configs/:configId/nodes/:nodeId/control` 为节点端点控制
- `/configs` 重定向到 `/`
- `/backups` 重定向到 `/settings`

## 手动运行

安装依赖：

```powershell
cd front
pnpm install
```

启动开发服务：

```powershell
cd front
pnpm run dev
```

访问：

- 前端：`http://127.0.0.1:5173`
- 开发态 `/api` 会代理到 `http://127.0.0.1:8000`

## 检查与构建

类型检查：

```powershell
cd front
pnpm run typecheck
```

生成生产产物：

```powershell
cd front
pnpm run build
```

构建完成后会生成 `front/dist`，供后端或 Docker 直接托管。
