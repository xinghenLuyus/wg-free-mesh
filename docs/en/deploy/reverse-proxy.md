# Reverse Proxy

Production deployments should use HTTPS. WG Free Mesh does not issue certificates or terminate TLS by itself; use Nginx, Caddy, or a cloud gateway for that layer.

Docker only needs to expose the gateway Web port, for example `127.0.0.1:8000` on the host. The external reverse proxy forwards public HTTPS traffic to that port.

Set the public origin before deployment:

```env
WFM_PUBLIC_ORIGIN=https://wfm.example.com
```

## Nginx

This example forwards `https://wfm.example.com` to the Docker gateway on local port `8000`.

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

`proxy_buffering off` matters for SSE. Without it, realtime events may be delayed by proxy buffering.

## Caddy

Caddy can automatically issue and renew certificates.

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

## MQTT Ports

The HTTP reverse proxy handles the console, API, SSE, and MCP. MQTT is a separate TCP connection and does not share the HTTPS port.

If clients need to connect to MQTT from the public internet, configure the Docker `.env` ports and open them in the firewall or cloud security group:

```env
WFM_MQTT_PUBLIC_PORT=1883
WFM_MQTT_PUBLIC_TLS_PORT=8883
WFM_MQTT_TLS_ENABLED=true
```

For production, prefer exposing the TLS port. Plain MQTT is only suitable for private or controlled networks.

## Checklist

- Browser access must match `WFM_PUBLIC_ORIGIN`.
- The reverse proxy must preserve the original `Host`.
- If snapshot upload fails, check both the proxy body limit and `WFM_GATEWAY_CLIENT_MAX_BODY_SIZE`.
- If SSE updates are delayed, check that proxy buffering is disabled.
