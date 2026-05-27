# 反向代理

生产环境强烈建议开启 HTTPS。WG Free Mesh 自身不负责证书签发和 TLS 终止，推荐由 Nginx、Caddy 或云厂商网关处理。

Docker 内部仍然只需要暴露 gateway 的 Web 端口，例如宿主机 `127.0.0.1:8000`。外部反向代理负责把公网 HTTPS 请求转发到这个端口。

部署前先把主来源改成公网 HTTPS 地址：

```env
WFM_PUBLIC_ORIGIN=https://wfm.example.com
```

## Nginx

下面示例把 `https://wfm.example.com` 转发到本机 Docker gateway 的 `8000` 端口。

```nginx
server {
    listen 80;
    server_name wfm.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name wfm.example.com;

    ssl_certificate /etc/nginx/certs/wfm.example.com.crt;
    ssl_certificate_key /etc/nginx/certs/wfm.example.com.key;

    client_max_body_size 512m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;

        proxy_buffering off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

`proxy_buffering off` 对 SSE 很重要，否则实时事件可能被代理缓冲。

## Caddy

Caddy 可以自动申请和续期证书。

```caddy
wfm.example.com {
    encode gzip

    request_body {
        max_size 512MB
    }

    reverse_proxy 127.0.0.1:8000 {
        header_up Host {host}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-Proto https
        flush_interval -1
    }
}
```

## MQTT 端口

HTTP 反向代理只处理控制台、API、SSE 和 MCP。MQTT 是独立 TCP 连接，不和 HTTPS 共用一个端口。

如果需要客户端从公网连接 MQTT，请在 Docker `.env` 中配置对应端口，并在防火墙或云安全组中放行：

```env
WFM_MQTT_PUBLIC_PORT=1883
WFM_MQTT_PUBLIC_TLS_PORT=8883
WFM_MQTT_TLS_ENABLED=true
```

生产环境更推荐暴露 TLS 端口。明文 MQTT 只适合内网或受控环境。

## 常见检查

- 浏览器访问地址必须和 `WFM_PUBLIC_ORIGIN` 一致。
- 反向代理必须保留原始 `Host`。
- 上传快照失败时，同时检查代理的请求体限制和 `WFM_GATEWAY_CLIENT_MAX_BODY_SIZE`。
- SSE 不实时刷新时，检查代理缓冲是否关闭。
