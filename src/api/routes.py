import uuid
import msgspec
from litestar import Controller, get, post, put, delete
from litestar.di import Provide
from litestar.exceptions import NotFoundException
from src.core.registry_sql import RegistrySQL as Registry
from src.core.registry import EventBus
from src.core.models import Route, Upstream, HealthCheck, Middleware, Certificate, Project, Application, Deployment, GitRepo, Secret
from src.docker_manager.manager import DockerManager
from src.acme.client import ACMEClient
from src.deployment.engine import DeploymentEngine
from src.api.schemas import (
    RouteCreate, RouteUpdate, NetworkCreate, MiddlewareCreate,
    CertificateRequest, StatusResponse, StatsResponse,
    ProjectCreate, ProjectUpdate, ApplicationCreate, ApplicationUpdate, DeployRequest, RollbackRequest, DeployLocalRequest,
    GitRepoCreate, GitRepoUpdate, SecretCreate
)

# ... (Controllers)

class CertificatesController(Controller):
    path = "/api/v1/certificates"
    
    @get("/")
    async def list_certificates(self, registry: Registry) -> list[Certificate]:
        return await registry.get_all_certificates()
    
    @get("/{domain:str}")
    async def get_certificate(self, domain: str, registry: Registry) -> Certificate:
        cert = await registry.get_certificate(domain)
        if not cert:
            raise NotFoundException(f"certificate for {domain} not found")
        return cert
    
    @post("/")
    async def request_certificate(self, data: CertificateRequest, acme_client: ACMEClient) -> Certificate:
        cert = await acme_client.obtain_certificate(data.domain)
        if not cert:
            raise NotFoundException(f"failed to obtain certificate for {data.domain}")
        return cert

# ...

class StatsController(Controller):
    path = "/api/v1"
    
    @get("/stats")
    async def get_stats(self, registry: Registry) -> StatsResponse:
        routes = await registry.get_all_routes()
        containers = await registry.get_all_containers()
        networks = await registry.get_all_networks()
        projects = await registry.get_all_projects()
        applications = await registry.get_all_applications()
        repos = await registry.get_all_git_repos()
        certs = await registry.get_all_certificates()
        return StatsResponse(
            routes=len(routes),
            certificates=len(certs),
            containers=len(containers),
            networks=len(networks),
            projects=len(projects),
            applications=len(applications),
            repos=len(repos)
        )


class RoutesController(Controller):
    path = "/api/v1/routes"
    
    @get("/")
    async def list_routes(self, registry: Registry) -> list[Route]:
        return await registry.get_all_routes()
    
    @get("/{route_id:str}")
    async def get_route(self, route_id: str, registry: Registry) -> Route:
        route = await registry.get_route(route_id)
        if not route:
            raise NotFoundException(f"route {route_id} not found")
        return route
    
    @post("/")
    async def create_route(self, data: RouteCreate, registry: Registry) -> Route:
        route_id = data.id or f"manual-{uuid.uuid4().hex[:8]}"
        health_check = None
        if data.health_check:
            health_check = HealthCheck(
                type=data.health_check.type,
                path=data.health_check.path,
                interval=data.health_check.interval,
                timeout=data.health_check.timeout
            )
        route = Route(
            id=route_id,
            host=data.host,
            path=data.path,
            protocol=data.protocol,
            upstreams=[Upstream(address=u.address, port=u.port, weight=u.weight) for u in data.upstreams],
            middlewares=data.middlewares,
            load_balancer=data.load_balancer,
            health_check=health_check,
            strip_path=data.strip_path
        )
        await registry.set_route(route)
        return route
    
    @put("/{route_id:str}")
    async def update_route(self, route_id: str, data: RouteUpdate, registry: Registry) -> Route:
        route = await registry.get_route(route_id)
        if not route:
            raise NotFoundException(f"route {route_id} not found")
        if data.host is not None:
            route.host = data.host
        if data.path is not None:
            route.path = data.path
        if data.protocol is not None:
            route.protocol = data.protocol
        if data.upstreams is not None:
            route.upstreams = [Upstream(address=u.address, port=u.port, weight=u.weight) for u in data.upstreams]
        if data.middlewares is not None:
            route.middlewares = data.middlewares
        if data.load_balancer is not None:
            route.load_balancer = data.load_balancer
        if data.enabled is not None:
            route.enabled = data.enabled
        await registry.set_route(route)
        return route
    
    @delete("/{route_id:str}", status_code=200)
    async def delete_route(self, route_id: str, registry: Registry) -> StatusResponse:
        deleted = await registry.delete_route(route_id)
        if not deleted:
            raise NotFoundException(f"route {route_id} not found")
        return StatusResponse(status="deleted")

class NetworksController(Controller):
    path = "/api/v1/networks"
    
    @get("/")
    async def list_networks(self, docker_manager: DockerManager) -> list:
        return await docker_manager.list_networks()
    
    @get("/{network_id:str}")
    async def get_network(self, network_id: str, docker_manager: DockerManager) -> dict:
        network = await docker_manager.get_network(network_id)
        if not network:
            raise NotFoundException(f"network {network_id} not found")
        return network
    
    @post("/")
    async def create_network(self, data: NetworkCreate, docker_manager: DockerManager) -> dict:
        return await docker_manager.create_network(
            name=data.name,
            driver=data.driver,
            subnet=data.subnet,
            gateway=data.gateway,
            internal=data.internal
        )
    
    @delete("/{network_id:str}", status_code=200)
    async def delete_network(self, network_id: str, docker_manager: DockerManager) -> StatusResponse:
        deleted = await docker_manager.delete_network(network_id)
        if not deleted:
            raise NotFoundException(f"network {network_id} not found")
        return StatusResponse(status="deleted")
    
    @post("/{network_id:str}/connect/{container_id:str}")
    async def connect_container(self, network_id: str, container_id: str, docker_manager: DockerManager) -> StatusResponse:
        success = await docker_manager.connect_container(network_id, container_id)
        return StatusResponse(status="connected" if success else "failed")
    
    @post("/{network_id:str}/disconnect/{container_id:str}")
    async def disconnect_container(self, network_id: str, container_id: str, docker_manager: DockerManager) -> StatusResponse:
        success = await docker_manager.disconnect_container(network_id, container_id)
        return StatusResponse(status="disconnected" if success else "failed")

class ContainersController(Controller):
    path = "/api/v1/containers"
    
    @get("/")
    async def list_containers(self, docker_manager: DockerManager) -> list:
        return await docker_manager.list_containers()
    
    @get("/{container_id:str}")
    async def get_container(self, container_id: str, docker_manager: DockerManager) -> dict:
        container = await docker_manager.get_container(container_id)
        if not container:
            raise NotFoundException(f"container {container_id} not found")
        return container
    
    @post("/{container_id:str}/start")
    async def start_container(self, container_id: str, docker_manager: DockerManager) -> StatusResponse:
        success = await docker_manager.start_container(container_id)
        return StatusResponse(status="started" if success else "failed")
    
    @post("/{container_id:str}/stop")
    async def stop_container(self, container_id: str, docker_manager: DockerManager) -> StatusResponse:
        success = await docker_manager.stop_container(container_id)
        return StatusResponse(status="stopped" if success else "failed")
    
    @post("/{container_id:str}/restart")
    async def restart_container(self, container_id: str, docker_manager: DockerManager) -> StatusResponse:
        success = await docker_manager.restart_container(container_id)
        return StatusResponse(status="restarted" if success else "failed")
    
    @get("/{container_id:str}/logs")
    async def get_logs(self, container_id: str, docker_manager: DockerManager, tail: int = 100) -> dict:
        logs = await docker_manager.get_container_logs(container_id, tail)
        return {"logs": logs}

class CertificatesController(Controller):
    path = "/api/v1/certificates"
    
    @get("/")
    async def list_certificates(self, registry: Registry) -> list[Certificate]:
        return await registry.get_all_certificates()
    
    @get("/{domain:str}")
    async def get_certificate(self, domain: str, registry: Registry) -> Certificate:
        cert = await registry.get_certificate(domain)
        if not cert:
            raise NotFoundException(f"certificate for {domain} not found")
        return cert
    
    @post("/")
    async def request_certificate(self, data: CertificateRequest, acme_client: ACMEClient) -> Certificate:
        cert = await acme_client.obtain_certificate(data.domain)
        if not cert:
            raise NotFoundException(f"failed to obtain certificate for {data.domain}")
        return cert

class MiddlewaresController(Controller):
    path = "/api/v1/middlewares"
    
    @get("/{name:str}")
    async def get_middleware(self, name: str, registry: Registry) -> Middleware:
        mw = await registry.get_middleware(name)
        if not mw:
            raise NotFoundException(f"middleware {name} not found")
        return mw
    
    @post("/")
    async def create_middleware(self, data: MiddlewareCreate, registry: Registry) -> Middleware:
        mw = Middleware(name=data.name, type=data.type, config=data.config)
        await registry.set_middleware(mw)
        return mw

class ProjectsController(Controller):
    path = "/api/v1/projects"
    
    @get("/")
    async def list_projects(self, registry: Registry) -> list[Project]:
        try:
            return await registry.get_all_projects()
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception("Error listing projects")
            raise e
    
    @get("/{project_id:str}")
    async def get_project(self, project_id: str, registry: Registry) -> Project:
        project = await registry.get_project(project_id)
        if not project:
            raise NotFoundException(f"project {project_id} not found")
        return project
    
    @post("/")
    async def create_project(self, data: ProjectCreate, registry: Registry) -> Project:
        project_id = data.id or f"proj-{uuid.uuid4().hex[:8]}"
        project = Project(id=project_id, name=data.name, description=data.description, env=data.env)
        await registry.set_project(project)
        return project
    
    @put("/{project_id:str}")
    async def update_project(self, project_id: str, data: ProjectUpdate, registry: Registry) -> Project:
        project = await registry.get_project(project_id)
        if not project:
            raise NotFoundException(f"project {project_id} not found")
        updates = {}
        if data.name is not None:
            updates["name"] = data.name
        if data.description is not None:
            updates["description"] = data.description
        if data.source_path is not None:
            updates["source_path"] = data.source_path
        if data.env is not None:
            updates["env"] = data.env
        project = Project(**{**msgspec.structs.asdict(project), **updates})
        await registry.set_project(project)
        return project
    
    @delete("/{project_id:str}", status_code=200)
    async def delete_project(self, project_id: str, registry: Registry, deploy_engine: DeploymentEngine) -> StatusResponse:
        apps = await registry.get_project_applications(project_id)
        for app in apps:
            await deploy_engine.remove_app(app)
            await registry.delete_application(app.id)
        deleted = await registry.delete_project(project_id)
        if not deleted:
            raise NotFoundException(f"project {project_id} not found")
        return StatusResponse(status="deleted")
    
    @get("/{project_id:str}/applications")
    async def get_project_apps(self, project_id: str, registry: Registry) -> list[Application]:
        return await registry.get_project_applications(project_id)

    @post("/{project_id:str}/deploy")
    async def deploy_project(self, project_id: str, registry: Registry, deploy_engine: DeploymentEngine) -> StatusResponse:
        project = await registry.get_project(project_id)
        if not project:
            raise NotFoundException(f"project {project_id} not found")
            
        # 1. Check if Git Repo linked
        repos = await registry.get_all_git_repos()
        linked_repo = next((r for r in repos if r.project_id == project_id), None)
        
        if linked_repo:
             await deploy_engine.deploy_from_repo(linked_repo)
             return StatusResponse(status="deploying")
             
        # 2. Check source_path
        if project.source_path:
             from src.api.routes import DeployLocalRequest, DeployController
             # Read files
             import yaml
             from pathlib import Path
             
             path = Path(project.source_path)
             if not path.exists():
                 raise NotFoundException(f"Source path {path} no longer exists")
                 
             compose_path = path / "docker-compose.yml"
             if not compose_path.exists():
                 compose_path = path / "docker-compose.yaml"
             
             if not compose_path.exists():
                  raise NotFoundException("docker-compose.yml not found")

             with open(compose_path) as f:
                compose_config = yaml.safe_load(f)
                
             deploy_config = {}
             for fname in ["deploy.yaml", "deploy.yml"]:
                dpath = path / fname
                if dpath.exists():
                    with open(dpath) as f:
                        deploy_config = yaml.safe_load(f)
                    break
             
             if not deploy_config:
                 deploy_config = {
                    "id": project.id,
                    "name": project.name, # Keep existing name
                    "services": {}
                 }
            
             cfg = {
                "deploy_config": deploy_config,
                "compose_config": compose_config,
                "_repo_dir": str(path)
             }
             await deploy_engine.deploy_from_config(cfg)
             return StatusResponse(status="deploying")
             
        raise NotFoundException("No deployment source (Git or Local Path) found for this project")

    @post("/{project_id:str}/restart")
    async def restart_project(self, project_id: str, registry: Registry, docker_manager: DockerManager) -> StatusResponse:
        apps = await registry.get_project_applications(project_id)
        for app in apps:
            for cid in app.container_ids:
                await docker_manager.restart_container(cid)
        return StatusResponse(status="restarted")

    @post("/{project_id:str}/deploy")
    async def deploy_project(self, project_id: str, registry: Registry, deploy_engine: DeploymentEngine) -> StatusResponse:
        project = await registry.get_project(project_id)
        if not project:
            raise NotFoundException(f"project {project_id} not found")
            
        # 1. Check if Git Repo linked
        repos = await registry.get_all_git_repos()
        linked_repo = next((r for r in repos if r.project_id == project_id), None)
        
        if linked_repo:
             await deploy_engine.deploy_from_repo(linked_repo)
             return StatusResponse(status="deploying")
             
        # 2. Check source_path
        if project.source_path:
             from src.api.routes import DeployLocalRequest, DeployController
             # Re-use logic or call engine directly? 
             # Let's call a helper or duplicate minimal logic to read files.
             import yaml
             from pathlib import Path
             
             path = Path(project.source_path)
             if not path.exists():
                 raise NotFoundException(f"Source path {path} no longer exists")
                 
             compose_path = path / "docker-compose.yml"
             if not compose_path.exists():
                 compose_path = path / "docker-compose.yaml"
             
             if not compose_path.exists():
                  raise NotFoundException("docker-compose.yml not found")

             with open(compose_path) as f:
                compose_config = yaml.safe_load(f)
                
             deploy_config = {}
             for fname in ["deploy.yaml", "deploy.yml"]:
                dpath = path / fname
                if dpath.exists():
                    with open(dpath) as f:
                        deploy_config = yaml.safe_load(f)
                    break
             
             if not deploy_config:
                 deploy_config = {
                    "id": project.id,
                    "name": project.name, # Keep existing name
                    "services": {}
                 }
            
             cfg = {
                "deploy_config": deploy_config,
                "compose_config": compose_config,
                "_repo_dir": str(path)
             }
             await deploy_engine.deploy_from_config(cfg)
             return StatusResponse(status="deploying")
             
        raise NotFoundException("No deployment source (Git or Local Path) found for this project")

    @post("/{project_id:str}/restart")
    async def restart_project(self, project_id: str, registry: Registry, docker_manager: DockerManager) -> StatusResponse:
        apps = await registry.get_project_applications(project_id)
        for app in apps:
            for cid in app.container_ids:
                await docker_manager.restart_container(cid)
        return StatusResponse(status="restarted")

class ApplicationsController(Controller):
    path = "/api/v1/applications"
    
    @get("/")
    async def list_applications(self, registry: Registry) -> list[Application]:
        return await registry.get_all_applications()
    
    @get("/{app_id:str}")
    async def get_application(self, app_id: str, registry: Registry) -> Application:
        app = await registry.get_application(app_id)
        if not app:
            raise NotFoundException(f"application {app_id} not found")
        return app
    
    @post("/")
    async def create_application(self, data: ApplicationCreate, registry: Registry, deploy_engine: DeploymentEngine) -> Application:
        app_id = data.id or f"app-{uuid.uuid4().hex[:8]}"
        app = Application(
            id=app_id,
            project_id=data.project_id,
            name=data.name,
            source=data.source,
            source_url=data.source_url,
            source_branch=data.source_branch,
            dockerfile=data.dockerfile,
            build_context=data.build_context,
            image=data.image,
            compose_file=data.compose_file,
            domain=data.domain,
            port=data.port,
            env=data.env,
            volumes=data.volumes,
            networks=data.networks,
            replicas=data.replicas,
        )
        await registry.set_application(app)
        return app
    
    @put("/{app_id:str}")
    async def update_application(self, app_id: str, data: ApplicationUpdate, registry: Registry) -> Application:
        app = await registry.get_application(app_id)
        if not app:
            raise NotFoundException(f"application {app_id} not found")
        updates = {}
        for field in ["name", "source_url", "source_branch", "dockerfile", "image", "domain", "port", "env", "volumes", "replicas"]:
            val = getattr(data, field, None)
            if val is not None:
                updates[field] = val
        app = Application(**{**msgspec.structs.asdict(app), **updates})
        await registry.set_application(app)
        return app
    
    @delete("/{app_id:str}", status_code=200)
    async def delete_application(self, app_id: str, registry: Registry, deploy_engine: DeploymentEngine) -> StatusResponse:
        app = await registry.get_application(app_id)
        if not app:
            raise NotFoundException(f"application {app_id} not found")
        await deploy_engine.remove_app(app)
        await registry.delete_application(app_id)
        return StatusResponse(status="deleted")
    
    @post("/{app_id:str}/deploy")
    async def deploy_application(self, app_id: str, registry: Registry, deploy_engine: DeploymentEngine) -> Deployment:
        app = await registry.get_application(app_id)
        if not app:
            raise NotFoundException(f"application {app_id} not found")
        return await deploy_engine.deploy(app)
    
    @post("/{app_id:str}/stop")
    async def stop_application(self, app_id: str, registry: Registry, deploy_engine: DeploymentEngine) -> StatusResponse:
        app = await registry.get_application(app_id)
        if not app:
            raise NotFoundException(f"application {app_id} not found")
        await deploy_engine.stop_app(app)
        return StatusResponse(status="stopped")
    
    @post("/{app_id:str}/rollback")
    async def rollback_application(self, app_id: str, data: RollbackRequest, registry: Registry, deploy_engine: DeploymentEngine) -> Deployment:
        app = await registry.get_application(app_id)
        if not app:
            raise NotFoundException(f"application {app_id} not found")
        deploy = await deploy_engine.rollback(app, data.version)
        if not deploy:
            raise NotFoundException(f"rollback target v{data.version} not found")
        return deploy
    
    @get("/{app_id:str}/deployments")
    async def get_deployments(self, app_id: str, registry: Registry) -> list[Deployment]:
        return await registry.get_app_deployments(app_id)
    
    @get("/{app_id:str}/logs")
    async def get_logs(self, app_id: str, docker_manager: DockerManager, tail: int = 100) -> dict:
        container_ids = await docker_manager.get_app_container_ids(app_id)
        logs = {}
        for cid in container_ids:
            logs[cid] = await docker_manager.get_container_logs(cid, tail)
        return {"logs": logs}

    @get("/{app_id:str}/deploy-logs")
    async def get_deploy_logs(self, app_id: str, registry: Registry) -> dict:
        deployments = await registry.get_app_deployments(app_id, limit=1)
        if not deployments:
            return {"logs": "No deployments found."}
        latest = deployments[0]
        return {"logs": latest.logs, "status": latest.status, "version": latest.version}

class DeployController(Controller):
    path = "/api/v1/deploy"
    
    @post("/yaml")
    async def deploy_yaml(self, data: DeployRequest, deploy_engine: DeploymentEngine) -> dict:
        if not data.deploy_content or not data.compose_content:
            raise NotFoundException("deploy_content and compose_content required")
        import yaml
        deploy_config = yaml.safe_load(data.deploy_content)
        compose_config = yaml.safe_load(data.compose_content)
        
        cfg = {
            "deploy_config": deploy_config,
            "compose_config": compose_config
        }
        apps = await deploy_engine.deploy_from_config(cfg)
        return {"status": "deploying", "applications": [a.id for a in apps]}

    @post("/local")
    async def deploy_local(self, data: DeployLocalRequest, deploy_engine: DeploymentEngine) -> dict:
        import os
        import yaml
        from pathlib import Path
        
        path = Path(data.path)
        if not path.exists() or not path.is_dir():
             raise NotFoundException(f"path {data.path} does not exist or is not a directory")
             
        compose_path = path / "docker-compose.yml"
        if not compose_path.exists():
            compose_path = path / "docker-compose.yaml"
            if not compose_path.exists():
                 raise NotFoundException("docker-compose.yml not found in path")
        
        with open(compose_path) as f:
            compose_config = yaml.safe_load(f)
            
        # Try to load deploy.yaml, otherwise infer
        deploy_config = {}
        for fname in ["deploy.yaml", "deploy.yml"]:
            dpath = path / fname
            if dpath.exists():
                with open(dpath) as f:
                    deploy_config = yaml.safe_load(f)
                break
        
        if not deploy_config:
            # Auto-generate minimal deploy config
            project_id = path.name.lower().replace(" ", "-").replace("_", "-")
            deploy_config = {
                "id": project_id,
                "name": path.name,
                "services": {}
            }
            
        cfg = {
            "deploy_config": deploy_config,
            "compose_config": compose_config,
            "_repo_dir": str(path) # Use local path as repo_dir for context
        }
        
        apps = await deploy_engine.deploy_from_config(cfg)
        return {"status": "deploying", "applications": [a.id for a in apps]}

class GitReposController(Controller):
    path = "/api/v1/repos"
    
    @get("/")
    async def list_repos(self, registry: Registry) -> list[GitRepo]:
        return await registry.get_all_git_repos()
    
    @get("/{repo_id:str}")
    async def get_repo(self, repo_id: str, registry: Registry) -> GitRepo:
        repo = await registry.get_git_repo(repo_id)
        if not repo:
            raise NotFoundException(f"repo {repo_id} not found")
        return repo
    
    @post("/")
    async def create_repo(self, data: GitRepoCreate, registry: Registry) -> GitRepo:
        repo_id = data.id or f"repo-{uuid.uuid4().hex[:8]}"
        repo = GitRepo(
            id=repo_id,
            provider=data.provider,
            url=data.url,
            branch=data.branch,
            config_file=data.config_file,
            webhook_secret=data.webhook_secret,
        )
        await registry.set_git_repo(repo)
        return repo
    
    @put("/{repo_id:str}")
    async def update_repo(self, repo_id: str, data: GitRepoUpdate, registry: Registry) -> GitRepo:
        repo = await registry.get_git_repo(repo_id)
        if not repo:
            raise NotFoundException(f"repo {repo_id} not found")
        updates = {}
        for field in ["branch", "config_file", "webhook_secret", "enabled"]:
            val = getattr(data, field, None)
            if val is not None:
                updates[field] = val
        repo = GitRepo(**{**msgspec.structs.asdict(repo), **updates})
        await registry.set_git_repo(repo)
        return repo
    
    @delete("/{repo_id:str}", status_code=200)
    async def delete_repo(self, repo_id: str, registry: Registry) -> StatusResponse:
        deleted = await registry.delete_git_repo(repo_id)
        if not deleted:
            raise NotFoundException(f"repo {repo_id} not found")
        return StatusResponse(status="deleted")
    
    @post("/{repo_id:str}/deploy")
    async def deploy_repo(self, repo_id: str, registry: Registry, deploy_engine: DeploymentEngine) -> dict:
        repo = await registry.get_git_repo(repo_id)
        if not repo:
            raise NotFoundException(f"repo {repo_id} not found")
        apps = await deploy_engine.deploy_from_repo(repo)
        return {"status": "deploying", "applications": [a.id for a in apps]}

class SecretsController(Controller):
    path = "/api/v1/secrets"
    
    @get("/{project_id:str}")
    async def list_secrets(self, project_id: str, registry: Registry) -> list[dict]:
        secrets = await registry.get_project_secrets(project_id)
        return [{"name": s.name, "created_at": s.created_at} for s in secrets]
    
    @post("/")
    async def create_secret(self, data: SecretCreate, registry: Registry) -> StatusResponse:
        secret = Secret(
            id=f"{data.project_id}-{data.name}",
            project_id=data.project_id,
            name=data.name,
            value=data.value,
        )
        await registry.set_secret(secret)
        return StatusResponse(status="created")
    
    @delete("/{project_id:str}/{name:str}", status_code=200)
    async def delete_secret(self, project_id: str, name: str, registry: Registry) -> StatusResponse:
        deleted = await registry.delete_secret(project_id, name)
        if not deleted:
            raise NotFoundException(f"secret {name} not found")
        return StatusResponse(status="deleted")

class WebhookController(Controller):
    path = "/api/v1/webhook"
    
    @post("/github")
    async def github_webhook(self, data: dict, registry: Registry, event_bus: EventBus) -> dict:
        from litestar import Request
        from src.webhook.handler import WebhookHandler
        handler = WebhookHandler(registry, event_bus)
        signature = ""
        return await handler.handle_github(data, signature)
    
    @post("/gitlab")
    async def gitlab_webhook(self, data: dict, registry: Registry, event_bus: EventBus) -> dict:
        from src.webhook.handler import WebhookHandler
        handler = WebhookHandler(registry, event_bus)
        token = ""
        return await handler.handle_gitlab(data, token)
    
    @post("/gitea")
    async def gitea_webhook(self, data: dict, registry: Registry, event_bus: EventBus) -> dict:
        from src.webhook.handler import WebhookHandler
        handler = WebhookHandler(registry, event_bus)
        return await handler.handle_gitea(data, "")

class StatsController(Controller):
    path = "/api/v1"
    
    @get("/stats")
    async def get_stats(self, registry: Registry) -> StatsResponse:
        routes = await registry.get_all_routes()
        containers = await registry.get_all_containers()
        networks = await registry.get_all_networks()
        projects = await registry.get_all_projects()
        applications = await registry.get_all_applications()
        repos = await registry.get_all_git_repos()
        certs = await registry.get_all_certificates()
        cert_count = len(certs)
        return StatsResponse(
            routes=len(routes),
            certificates=cert_count,
            containers=len(containers),
            networks=len(networks),
            projects=len(projects),
            applications=len(applications),
            repos=len(repos)
        )
    
    @get("/health")
    async def health(self) -> StatusResponse:
        return StatusResponse(status="ok")

class SystemController(Controller):
    path = "/api/v1/system"
    
    @post("/restart")
    async def restart_system(self) -> StatusResponse:
        import sys
        import asyncio
        # Schedule exit slightly in future to allow response to send
        async def _exit():
            await asyncio.sleep(1)
            sys.exit(1) # Supervisor should restart
        asyncio.create_task(_exit())
        return StatusResponse(status="restarting")

    @get("/info")
    async def system_info(self) -> dict:
        import platform
        import psutil
        return {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent
        }
