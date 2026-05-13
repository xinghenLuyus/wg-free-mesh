FROM node:22-alpine AS front-build

WORKDIR /front

COPY front/package.json front/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile

COPY front ./
RUN pnpm run build

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates golang-go \
    && rm -rf /var/lib/apt/lists/*

COPY client/go.mod client/go.sum /client/
RUN cd /client && go mod download
COPY client /client

COPY src/pyproject.toml src/README.md ./
COPY src/app ./app
COPY --from=front-build /front/dist /front/dist

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "1"]
