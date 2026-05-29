# Quick Start

The simplest path is the Docker SQLite deployment.

## Start

Clone the repository first:

```bash
git clone https://github.com/xinghenLuyus/wg-free-mesh.git
cd wg-free-mesh
```

Enter the Docker SQLite directory:

```bash
cd docker/sqlite
```

Copy the environment file:

```bash
cp .env.example .env
```

Start the services:

```bash
docker compose up -d
```

After startup, open:

```text
http://localhost:8000
```

## Initialize

On the first visit, follow the setup page and create the administrator password.

After initialization, create a config, add nodes, then download the client and bind nodes.

## Next steps

- To create a network, read [First Mesh](./first-mesh).
- For deployment details, read [Docker Deploy](/en/deploy/).
