# 快速开始

最简单的方式是直接启动 SQLite 版本。

## 启动

先克隆项目代码：

```bash
git clone https://github.com/xinghenLuyus/wg-free-mesh.git
cd wg-free-mesh
```

进入 Docker SQLite 目录：

```bash
cd docker/sqlite
```

复制环境变量文件：

```bash
cp .env.example .env
```

启动服务：

```bash
docker compose up -d
```

启动完成后，打开：

```text
http://localhost:8000
```

## 初始化

第一次进入页面时，按照初始化界面完成管理员密码设置。

初始化完成后，进入控制台创建配置、添加端点，然后下载客户端并绑定节点。

## 下一步

- 继续创建网络：阅读 [第一个 Mesh](./first-mesh)。
- 了解部署细节：阅读 [Docker 部署](/deploy/)。
