import msgspec
from enum import Enum

class Protocol(str, Enum):
    HTTP = "http"
    HTTPS = "https"
    TCP = "tcp"
    UDP = "udp"

class HealthCheckType(str, Enum):
    HTTP = "http"
    TCP = "tcp"
    NONE = "none"

class LoadBalancer(str, Enum):
    ROUND_ROBIN = "round_robin"
    LEAST_CONN = "least_conn"
    IP_HASH = "ip_hash"
    RANDOM = "random"

class DeploySource(str, Enum):
    GIT = "git"
    IMAGE = "image"
    COMPOSE = "compose"

class DeployStatus(str, Enum):
    PENDING = "pending"
    BUILDING = "building"
    DEPLOYING = "deploying"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"

class HealthCheck(msgspec.Struct):
    type: HealthCheckType = HealthCheckType.HTTP
    path: str = "/"
    interval: int = 10
    timeout: int = 5
    healthy_threshold: int = 2
    unhealthy_threshold: int = 3

class Upstream(msgspec.Struct):
    address: str
    port: int
    weight: int = 1
    healthy: bool = True
    container_id: str | None = None

class Middleware(msgspec.Struct):
    name: str
    type: str
    config: dict

class Route(msgspec.Struct, kw_only=True):
    id: str
    host: str
    path: str = "/"
    protocol: Protocol = Protocol.HTTP
    upstreams: list[Upstream] = []
    middlewares: list[str] = []
    load_balancer: LoadBalancer = LoadBalancer.ROUND_ROBIN
    health_check: HealthCheck | None = None
    strip_path: bool = False
    preserve_host: bool = True
    enabled: bool = True

class Certificate(msgspec.Struct):
    domain: str
    cert_path: str
    key_path: str
    expires_at: int
    auto_renew: bool = True

class DockerNetwork(msgspec.Struct):
    id: str
    name: str
    driver: str
    scope: str = "local"
    subnet: str | None = None
    gateway: str | None = None
    containers: list[str] = []

class DockerContainer(msgspec.Struct):
    id: str
    name: str
    image: str
    status: str
    labels: dict
    networks: list[str]
    ip_addresses: dict[str, str] = {}

class Application(msgspec.Struct, kw_only=True):
    id: str
    project_id: str
    name: str
    source: DeploySource
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
    healthcheck: dict | None = None
    status: DeployStatus = DeployStatus.PENDING
    container_ids: list[str] = []
    created_at: int = 0
    updated_at: int = 0

class Project(msgspec.Struct, kw_only=True):
    id: str
    name: str
    description: str = ""
    source_path: str = "" # For local path deployments
    env: dict[str, str] = {}
    created_at: int = 0
    updated_at: int = 0

class Deployment(msgspec.Struct, kw_only=True):
    id: str
    app_id: str
    version: int
    status: DeployStatus
    image: str = ""
    container_ids: list[str] = []
    logs: str = ""
    started_at: int = 0
    finished_at: int = 0

class GitProvider(str, Enum):
    GITHUB = "github"
    GITLAB = "gitlab"
    GITEA = "gitea"
    BITBUCKET = "bitbucket"

class GitRepo(msgspec.Struct, kw_only=True):
    id: str
    provider: GitProvider
    url: str
    branch: str = "main"
    config_file: str = "deploy.yaml"
    webhook_secret: str = ""
    project_id: str | None = None
    last_commit: str = ""
    last_deploy_at: int = 0
    enabled: bool = True
    created_at: int = 0

class Secret(msgspec.Struct, kw_only=True):
    id: str
    project_id: str
    name: str
    value: str
    created_at: int = 0
