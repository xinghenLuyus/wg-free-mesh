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

当前页面信息架构按 `bak` 收束：

- 左侧主导航：首页 / 设置 / 帮助 / 配置列表 / 退出登录 / 系统状态
- 配置子菜单：概览 / Mesh 网络 / 配置应用 / 端点控制
- 配置详情页承担节点主工作台职责
- 配置详情页提供配置编辑、启停和删除入口
- 节点维护页提供新增、编辑、删除、生成密钥和推荐虚拟 IP
- 备份恢复收纳在设置页

## 路由约定

- `/` 为首页
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
