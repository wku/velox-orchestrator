import msgspec
from src.core.models import Protocol, LoadBalancer, HealthCheckType, DeploySource, GitProvider

class UpstreamCreate(msgspec.Struct):
    address: str
    port: int
    weight: int = 1

class HealthCheckCreate(msgspec.Struct):
    type: HealthCheckType = HealthCheckType.HTTP
    path: str = "/"
    interval: int = 10
    timeout: int = 5

class RouteCreate(msgspec.Struct):
    host: str
    path: str = "/"
    protocol: Protocol = Protocol.HTTP
    upstreams: list[UpstreamCreate] = []
    middlewares: list[str] = []
    load_balancer: LoadBalancer = LoadBalancer.ROUND_ROBIN
    health_check: HealthCheckCreate | None = None
    strip_path: bool = False
    id: str | None = None

class RouteUpdate(msgspec.Struct):
    host: str | None = None
    path: str | None = None
    protocol: Protocol | None = None
    upstreams: list[UpstreamCreate] | None = None
    middlewares: list[str] | None = None
    load_balancer: LoadBalancer | None = None
    enabled: bool | None = None

class NetworkCreate(msgspec.Struct):
    name: str
    driver: str = "bridge"
    subnet: str | None = None
    gateway: str | None = None
    internal: bool = False

class MiddlewareCreate(msgspec.Struct):
    name: str
    type: str
    config: dict

class CertificateRequest(msgspec.Struct):
    domain: str

class StatusResponse(msgspec.Struct):
    status: str
    message: str | None = None

class StatsResponse(msgspec.Struct):
    routes: int
    certificates: int
    containers: int
    networks: int
    projects: int = 0
    applications: int = 0
    repos: int = 0

class ProjectCreate(msgspec.Struct):
    name: str
    description: str = ""
    env: dict[str, str] = {}
    id: str | None = None

class ProjectUpdate(msgspec.Struct):
    name: str | None = None
    description: str | None = None
    source_path: str | None = None
    env: dict[str, str] | None = None

class ApplicationCreate(msgspec.Struct):
    name: str
    project_id: str
    source: DeploySource = DeploySource.IMAGE
    source_url: str = ""
    source_branch: str = "main"
    dockerfile: str = "Dockerfile"
    build_context: str = "."
    image: str = ""
    compose_file: str = ""
    domain: str = ""
    port: int = 80
    env: dict[str, str] = {}
    volumes: list[str] = []
    networks: list[str] = []
    replicas: int = 1
    depends_on: list[str] = []
    id: str | None = None

class ApplicationUpdate(msgspec.Struct):
    name: str | None = None
    source_url: str | None = None
    source_branch: str | None = None
    dockerfile: str | None = None
    image: str | None = None
    domain: str | None = None
    port: int | None = None
    env: dict[str, str] | None = None
    volumes: list[str] | None = None
    replicas: int | None = None

class DeployRequest(msgspec.Struct):
    deploy_content: str
    compose_content: str

class DeployLocalRequest(msgspec.Struct):
    path: str

class RollbackRequest(msgspec.Struct):
    version: int

class GitRepoCreate(msgspec.Struct):
    url: str
    provider: GitProvider = GitProvider.GITHUB
    branch: str = "main"
    config_file: str = "deploy.yaml"
    webhook_secret: str = ""
    id: str | None = None

class GitRepoUpdate(msgspec.Struct):
    branch: str | None = None
    config_file: str | None = None
    webhook_secret: str | None = None
    enabled: bool | None = None

class SecretCreate(msgspec.Struct):
    project_id: str
    name: str
    value: str
