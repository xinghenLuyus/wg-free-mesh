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

- 左侧主导航：首页 / 设置 / 帮助 / 配置列表 / 退出登录 / 系统状态
- 配置列表只显示配置名称，不展开子页面
- 配置概览页负责配置头和节点工作区
- 配置设置通过配置头右侧“设置”进入，删除配置放在设置弹窗内
- 节点卡片点击进入节点页面
- 节点列表视图仍叫“列表”，视觉使用横向长条卡片，不使用传统表格标题行
- 节点页面包含公共节点头和三个模板：Mesh 网络 / 配置应用 / 端点控制

## 界面约定

- 视觉方向是精致工具型控制台，保留当前业务布局，不擅自改变页面信息结构
- Element Plus 是唯一 UI 框架，结构性图标使用 `@element-plus/icons-vue`
- 全局按钮、输入框、弹窗、表格、卡片在 `src/assets/main.css` 中统一基础质感
- 配置、节点、快照等重复项目使用卡片或长条卡片，不用传统标题行列表承载主业务入口
- 弹窗表单需要有说明区、明确按钮层级和危险操作分区

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
