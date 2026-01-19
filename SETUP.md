# Velox Orchestrator Proxy Configuration Guide

## Domain Configuration

Velox Orchestrator Proxy supports both local development domains (using `.nip.io`) and production domains.

### 1. Local Development (Default)

By default, Velox Orchestrator uses `127.0.0.1.nip.io` as the base domain. No extra configuration is needed.

- **Frontend**: `http://localhost:5173`
- **Dashboard API**: `http://localhost:8000`
- **Deployed Services**: `{service}-{project}.127.0.0.1.nip.io`

### 2. Production Domain

To use a real domain (e.g., `example.com`), update `docker/docker-compose.yml`:

```yaml
services:
  control-plane:
    environment:
      - ROOT_DOMAIN=example.com
      - ACME_EMAIL=admin@example.com
      - ACME_STAGING=false  # Set false for real SSL certs
```

Then rebuild and restart:
```bash
cd docker
docker compose up -d --build vo-control
```

#### DNS Setup
You must configure your DNS provider (Cloudflare, GoDaddy, etc.) to point the following records to your server's public IP:

- `A` record: `example.com` -> `SERVER_IP`
- `A` record: `*.example.com` -> `SERVER_IP` (Wildcard is required for dynamic subdomains)

### 3. Custom Project Domains

In your project's `deploy.yaml`, you can specify custom domains:

```yaml
services:
  web:
    # Full domain (overrides ROOT_DOMAIN)
    domain: my-special-site.com
    port: 80
  
  api:
    # Short domain (becomes api.example.com)
    domain: api
    port: 8080
```

If `domain` is NOT specified, it auto-generates:
- `{service}-{project}.example.com`

## Troubleshooting

- **404 Not Found**: Routes are not in Redis. Try "Re-deploy".
- **Healthcheck Failed**: Check logs with detailed output enabled.
