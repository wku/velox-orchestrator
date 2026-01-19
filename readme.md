# Velox Orchestrator

Platform for fast container orchestration with dynamic proxying and continuous deployment without downtime

## Description

Velox Orchestrator provides a simple and efficient way to manage containerized applications with automatic traffic routing and updates without downtime. The system integrates with Git repositories for automatic deployment on every code update


## 1. Local Launch (Development)

### Prerequisites
* Docker Engine >= 24.0
* Docker Compose

### System Launch
1. Navigate to the `docker` folder:
   ```bash
   cd docker
   ```
2. Start the services:
   ```bash
   docker compose up -d --build

   docker compose up --build
   ```
   *The `--build` flag is important on the first launch to build the current control-plane image.*

3. Check API status:
   ```bash
   curl http://localhost:8000/api/v1/health
   # Expected response: {"status":"ok"}
   ```

### Running Examples (Demo)
In the `examples` folder, a script is prepared for deploying test applications (API + 2 static sites).

1. Navigate to the `examples` folder:
   ```bash
   cd ../examples
   ```
2. Run the deployment script:
   ```bash
   chmod +x deploy-demo.sh
   ./deploy-demo.sh
   ```
   *The script will build local Docker images and send the configuration (`demo-deploy.yaml` + `demo-compose.yml`) to the API.*

3. Check deployment status:
   ```bash
   curl http://localhost:8000/api/v1/applications/demo-api | jq
   ```
   Wait for `healthy` status.

4. Check service availability (using routing domain `127.0.0.1.nip.io`):
   ```bash
   # Demo API
   curl http://api.127.0.0.1.nip.io/health
   
   # Site 1
   curl -I http://site1.127.0.0.1.nip.io
   ```

### Working with Examples

#### Modification and Update (Redeploy)
You can modify the source code of any example and update it without downtime (Zero-Downtime).

For example, to modify `site2`:
1. Edit the file `examples/demo-site2/index.html` (or create it).
2. Run the deployment script again:
   ```bash
   ./deploy-demo.sh
   ```
   Orchestrator will automatically:
   - Build a new Docker image.
   - Start a new container.
   - Wait for Healthcheck to pass.
   - Switch traffic to the new version.
   - Stop the old version.

#### Stopping Services
To stop or remove a specific service, use the platform API.

**Stop service (Stop):**
The container will be stopped, but the configuration will remain in the system.
```bash
# Stop demo-site2
curl -X POST http://localhost:8000/api/v1/applications/demo-site2/stop
```

**Delete service (Delete):**
The service will be completely removed from the system, including containers and routes.
```bash
# Delete demo-site2
curl -X DELETE http://localhost:8000/api/v1/applications/demo-site2
```

### Stopping the System
To stop all services and remove containers:
```bash
cd ../docker
docker compose down
```

---

## 2. Server Launch (Production)

### Git Integration Setup (GitHub/GitLab)

The system supports automatic deployment when the Git repository is updated.

1. **Server Preparation**:
   Follow the steps from the "System Launch" section on your server. Make sure ports `80`, `443`, and `8000` are open.

2. **Repository Preparation**:
   In the root of your Git repository, there should be two files:
   * `docker-compose.yml` - Service description (images, healthchecks).
   * `deploy.yaml` - Velox Orchestrator routing configuration (domains, replicas).

3. **Repository Registration in Velox Orchestrator:**
   Execute a request to your server's API (for example, 1.2.3.4):
   ```bash
   curl -X POST http://1.2.3.4:8000/api/v1/repos \
     -H "Content-Type: application/json" \
     -d '{
       "url": "https://github.com/your-user/your-repo.git",
       "branch": "main",
       "provider": "github",
       "config_file": "deploy.yaml"
     }'
   ```
   *In the response, you will receive a `webhook_secret`. Save it.*

4. **Webhook Setup in GitHub**:
   * Go to `Settings` -> `Webhooks` -> `Add webhook`.
   * **Payload URL**: `http://1.2.3.4:8000/api/v1/webhook/github`
   * **Content type**: `application/json`
   * **Secret**: (Your secret from step 3)
   * **Events**: `Push events`
   * Click `Add webhook`.

Now with every `git push` to the `main` branch, Velox Orchestrator will automatically pull the updates and apply Zero-Downtime deployment.

---

## 3. Configuration File Requirements

### `docker-compose.yml`
```yaml
version: "3.8"
services:
  app:
    image: myregistry/myapp:latest
    environment:
      PORT: "8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 5s
      retries: 5
```

### `deploy.yaml`
```yaml
name: my-project
id: my-project

services:
  app:
    domain: myapp.com
    port: 8000
    replicas: 2
    update_strategy: rolling
```

## 4. Web Interface (Frontend)

The system includes a web interface for monitoring and management.

### Launch
```bash
cd front
npm install --legacy-peer-deps
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

### Access
- Login: `admin`
- Password: `admin`

For more details, see [front/README.md](front/README.md).