import asyncio
import logging
import sys
import socket
from contextlib import asynccontextmanager
from litestar import Litestar
from litestar.di import Provide
from src import config
from src.core.registry_sql import RegistrySQL
from src.core.registry import EventBus
from src.discovery.docker_provider import DockerProvider
from src.docker_manager.manager import DockerManager
from src.acme.client import ACMEClient
from src.deployment.engine import DeploymentEngine
from src.tasks.workers import HealthChecker, CertRenewalTask
from src.core.models import Route, Upstream, Protocol
from src.api.routes import (
    RoutesController, NetworksController, ContainersController,
    CertificatesController, MiddlewaresController, StatsController,
    ProjectsController, ApplicationsController, DeployController,
    GitReposController, SecretsController, WebhookController,
    SystemController
)

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout
)
log = logging.getLogger(__name__)

registry: RegistrySQL | None = None
event_bus: EventBus | None = None
docker_provider: DockerProvider | None = None
docker_manager: DockerManager | None = None
acme_client: ACMEClient | None = None
deploy_engine: DeploymentEngine | None = None
health_checker: HealthChecker | None = None
cert_renewal: CertRenewalTask | None = None

async def register_system_routes(registry: RegistrySQL):
    """Register routes for Velox Orchestrator frontend and vo-control (sys-api)"""
    # Frontend -> ROOT_DOMAIN
    try:
        # Resolve IP of Velox Orchestrator frontend container
        front_ip = socket.gethostbyname("vo-frontend")
        route_front = Route(
            id="system-frontend",
            host=config.ROOT_DOMAIN,
            upstreams=[Upstream(address=front_ip, port=5173)],
            protocol=Protocol.HTTP,
            preserve_host=True
        )
        await registry.set_route(route_front)
        log.info(f"system route set: {config.ROOT_DOMAIN} -> {front_ip}:5173")
    except Exception as e:
        log.warning(f"failed to set system-frontend route: {e}")

    # API -> sys-api.ROOT_DOMAIN
    try:
        # Resolve IP of vo-control (self)
        api_ip = socket.gethostbyname(socket.gethostname())
        api_domain = f"sys-api.{config.ROOT_DOMAIN}"
        route_api = Route(
            id="system-api",
            host=api_domain,
            upstreams=[Upstream(address=api_ip, port=8000)],
            protocol=Protocol.HTTP,
            preserve_host=True
        )
        await registry.set_route(route_api)
        log.info(f"system route set: {api_domain} -> {api_ip}:8000")
    except Exception as e:
        log.warning(f"failed to set system-api route: {e}")

async def get_registry() -> RegistrySQL:
    return registry

async def get_event_bus() -> EventBus:
    return event_bus

async def get_docker_manager() -> DockerManager:
    return docker_manager

async def get_acme_client() -> ACMEClient:
    return acme_client

async def get_deploy_engine() -> DeploymentEngine:
    return deploy_engine

from src.core.registry_sql import RegistrySQL

# ...
@asynccontextmanager
async def lifespan(app: Litestar):
    global registry, event_bus, docker_provider, docker_manager, acme_client, deploy_engine, health_checker, cert_renewal
    log.info("starting vo")
    # registry = Registry(config.REDIS_URL) # Old
    registry = RegistrySQL(config.DATABASE_URL) # New
    await registry.connect()
    event_bus = EventBus()
    docker_provider = DockerProvider(registry, event_bus)
    await docker_provider.start()
    docker_manager = DockerManager(registry)
    await docker_manager.start()
    acme_client = ACMEClient(registry)
    await acme_client.start()
    deploy_engine = DeploymentEngine(registry, event_bus)
    await deploy_engine.start()
    health_checker = HealthChecker(registry)
    await health_checker.start()
    cert_renewal = CertRenewalTask(acme_client)
    await cert_renewal.start()
    
    # Register system routes
    await register_system_routes(registry)
    
    log.info("vo started")
    yield
    log.info("stopping vo")
    await cert_renewal.stop()
    await health_checker.stop()
    await deploy_engine.stop()
    await acme_client.stop()
    await docker_manager.stop()
    await docker_provider.stop()
    await registry.close()
    log.info("vo stopped")

from src.api.auth import AuthController
from litestar.middleware.cors import CORSMiddleware
from litestar.config.cors import CORSConfig

app = Litestar(
    route_handlers=[
        RoutesController,
        NetworksController,
        ContainersController,
        CertificatesController,
        MiddlewaresController,
        ProjectsController,
        ApplicationsController,
        DeployController,
        GitReposController,
        SecretsController,
        WebhookController,
        StatsController,
        SystemController,
        AuthController
    ],
    dependencies={
        "registry": Provide(get_registry),
        "event_bus": Provide(get_event_bus),
        "docker_manager": Provide(get_docker_manager),
        "acme_client": Provide(get_acme_client),
        "deploy_engine": Provide(get_deploy_engine),
    },
    cors_config=CORSConfig(allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]),
    lifespan=[lifespan],
    debug=config.LOG_LEVEL == "DEBUG"
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=False
    )
