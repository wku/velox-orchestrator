import asyncio
import logging
import msgspec
import time
import redis.asyncio as redis
from typing import Callable, Any
from src.core.models import Route, Certificate, Middleware, DockerNetwork, DockerContainer, Project, Application, Deployment, GitRepo, Secret

log = logging.getLogger(__name__)

class EventBus:
    def __init__(self):
        self._handlers: dict[str, list[Callable]] = {}
    
    def on(self, event: str, handler: Callable) -> None:
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(handler)
    
    async def emit(self, event: str, data: Any = None) -> None:
        if event not in self._handlers:
            return
        for handler in self._handlers[event]:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                log.error(f"event handler error {event}: {e}")

class Registry:
    def __init__(self, redis_url: str):
        self.redis: redis.Redis | None = None
        self.redis_url = redis_url
        self.encoder = msgspec.json.Encoder()
        self._decoders = {
            Route: msgspec.json.Decoder(Route),
            Certificate: msgspec.json.Decoder(Certificate),
            Middleware: msgspec.json.Decoder(Middleware),
            DockerNetwork: msgspec.json.Decoder(DockerNetwork),
            DockerContainer: msgspec.json.Decoder(DockerContainer),
            Project: msgspec.json.Decoder(Project),
            Application: msgspec.json.Decoder(Application),
            Deployment: msgspec.json.Decoder(Deployment),
            GitRepo: msgspec.json.Decoder(GitRepo),
            Secret: msgspec.json.Decoder(Secret),
        }
    
    async def connect(self) -> None:
        self.redis = await redis.from_url(self.redis_url, decode_responses=False)
        log.info("redis connected")
    
    async def close(self) -> None:
        if self.redis:
            await self.redis.close()
    
    def _decode(self, data: bytes, typ: type):
        if not data:
            return None
        return self._decoders[typ].decode(data)
    
    async def set_route(self, route: Route) -> None:
        pipe = self.redis.pipeline()
        pipe.set(f"routes:{route.id}", self.encoder.encode(route))
        pipe.sadd(f"routes:index:host:{route.host}", route.id)
        if route.enabled:
            pipe.sadd("routes:index:enabled", route.id)
        else:
            pipe.srem("routes:index:enabled", route.id)
        pipe.delete(f"upstreams:{route.id}")
        for u in route.upstreams:
            pipe.rpush(f"upstreams:{route.id}", f"{u.address}:{u.port}:{u.weight}")
        pipe.incr("config:version")
        await pipe.execute()
        log.info(f"route set: {route.id} -> {route.host}{route.path}")
    
    async def get_route(self, route_id: str) -> Route | None:
        data = await self.redis.get(f"routes:{route_id}")
        return self._decode(data, Route)
    
    async def get_routes_by_host(self, host: str) -> list[Route]:
        route_ids = await self.redis.smembers(f"routes:index:host:{host}")
        if not route_ids:
            return []
        pipe = self.redis.pipeline()
        for rid in route_ids:
            rid_str = rid.decode() if isinstance(rid, bytes) else rid
            pipe.get(f"routes:{rid_str}")
        results = await pipe.execute()
        return [self._decode(r, Route) for r in results if r]
    
    async def get_all_routes(self) -> list[Route]:
        routes = []
        async for key in self.redis.scan_iter("routes:*"):
            key_str = key.decode() if isinstance(key, bytes) else key
            if ":index:" in key_str or ":upstreams:" in key_str:
                continue
            data = await self.redis.get(key)
            if data:
                routes.append(self._decode(data, Route))
        return routes
    
    async def delete_route(self, route_id: str) -> bool:
        route = await self.get_route(route_id)
        if not route:
            return False
        pipe = self.redis.pipeline()
        pipe.delete(f"routes:{route_id}")
        pipe.delete(f"upstreams:{route_id}")
        pipe.srem(f"routes:index:host:{route.host}", route_id)
        pipe.srem("routes:index:enabled", route_id)
        pipe.incr("config:version")
        await pipe.execute()
        log.info(f"route deleted: {route_id}")
        return True
    
    async def update_upstream_health(self, route_id: str, address: str, port: int, healthy: bool) -> None:
        status = "healthy" if healthy else "unhealthy"
        await self.redis.set(f"upstreams:health:{route_id}:{address}:{port}", status, ex=60)
    
    async def set_certificate(self, cert: Certificate) -> None:
        pipe = self.redis.pipeline()
        pipe.set(f"certs:{cert.domain}", self.encoder.encode(cert))
        pipe.zadd("certs:index:expiring", {cert.domain: cert.expires_at})
        await pipe.execute()
        log.info(f"certificate set: {cert.domain}")
    
    async def get_certificate(self, domain: str) -> Certificate | None:
        data = await self.redis.get(f"certs:{domain}")
        return self._decode(data, Certificate)
    
    async def get_expiring_certificates(self, before_timestamp: int) -> list[Certificate]:
        domains = await self.redis.zrangebyscore("certs:index:expiring", 0, before_timestamp)
        certs = []
        for domain in domains:
            domain_str = domain.decode() if isinstance(domain, bytes) else domain
            cert = await self.get_certificate(domain_str)
            if cert:
                certs.append(cert)
        return certs
    
    async def set_middleware(self, middleware: Middleware) -> None:
        await self.redis.set(f"middlewares:{middleware.name}", self.encoder.encode(middleware))
    
    async def get_middleware(self, name: str) -> Middleware | None:
        data = await self.redis.get(f"middlewares:{name}")
        return self._decode(data, Middleware)
    
    async def set_network(self, network: DockerNetwork) -> None:
        await self.redis.hset("docker:networks", network.id, self.encoder.encode(network))
    
    async def get_network(self, network_id: str) -> DockerNetwork | None:
        data = await self.redis.hget("docker:networks", network_id)
        return self._decode(data, DockerNetwork)
    
    async def get_all_networks(self) -> list[DockerNetwork]:
        data = await self.redis.hgetall("docker:networks")
        return [self._decode(v, DockerNetwork) for v in data.values()]
    
    async def delete_network(self, network_id: str) -> None:
        await self.redis.hdel("docker:networks", network_id)
    
    async def set_container(self, container: DockerContainer) -> None:
        await self.redis.hset("docker:containers", container.id, self.encoder.encode(container))
    
    async def get_container(self, container_id: str) -> DockerContainer | None:
        data = await self.redis.hget("docker:containers", container_id)
        return self._decode(data, DockerContainer)
    
    async def get_all_containers(self) -> list[DockerContainer]:
        data = await self.redis.hgetall("docker:containers")
        return [self._decode(v, DockerContainer) for v in data.values()]
    
    async def delete_container(self, container_id: str) -> None:
        await self.redis.hdel("docker:containers", container_id)
    
    async def set_acme_challenge(self, token: str, key_auth: str, ttl: int = 300) -> None:
        await self.redis.set(f"acme:challenge:{token}", key_auth, ex=ttl)
    
    async def get_acme_challenge(self, token: str) -> str | None:
        data = await self.redis.get(f"acme:challenge:{token}")
        return data.decode() if data else None
    
    async def delete_acme_challenge(self, token: str) -> None:
        await self.redis.delete(f"acme:challenge:{token}")

    async def set_project(self, project: Project) -> None:
        now = int(time.time())
        if not project.created_at:
            project = Project(id=project.id, name=project.name, description=project.description, env=project.env, created_at=now, updated_at=now)
        else:
            project = Project(id=project.id, name=project.name, description=project.description, env=project.env, created_at=project.created_at, updated_at=now)
        await self.redis.hset("projects", project.id, self.encoder.encode(project))
        log.info(f"project set: {project.id}")
    
    async def get_project(self, project_id: str) -> Project | None:
        data = await self.redis.hget("projects", project_id)
        return self._decode(data, Project)
    
    async def get_all_projects(self) -> list[Project]:
        data = await self.redis.hgetall("projects")
        return [self._decode(v, Project) for v in data.values()]
    
    async def delete_project(self, project_id: str) -> bool:
        result = await self.redis.hdel("projects", project_id)
        if result:
            log.info(f"project deleted: {project_id}")
        return bool(result)

    async def set_application(self, app: Application) -> None:
        now = int(time.time())
        if not app.created_at:
            app = Application(**{**msgspec.structs.asdict(app), "created_at": now, "updated_at": now})
        else:
            app = Application(**{**msgspec.structs.asdict(app), "updated_at": now})
        pipe = self.redis.pipeline()
        pipe.hset("applications", app.id, self.encoder.encode(app))
        pipe.sadd(f"projects:{app.project_id}:apps", app.id)
        await pipe.execute()
        log.info(f"application set: {app.id}")
    
    async def get_application(self, app_id: str) -> Application | None:
        data = await self.redis.hget("applications", app_id)
        return self._decode(data, Application)
    
    async def get_project_applications(self, project_id: str) -> list[Application]:
        app_ids = await self.redis.smembers(f"projects:{project_id}:apps")
        if not app_ids:
            return []
        pipe = self.redis.pipeline()
        for aid in app_ids:
            aid_str = aid.decode() if isinstance(aid, bytes) else aid
            pipe.hget("applications", aid_str)
        results = await pipe.execute()
        return [self._decode(r, Application) for r in results if r]
    
    async def get_all_applications(self) -> list[Application]:
        data = await self.redis.hgetall("applications")
        return [self._decode(v, Application) for v in data.values()]
    
    async def delete_application(self, app_id: str) -> bool:
        app = await self.get_application(app_id)
        if not app:
            return False
        pipe = self.redis.pipeline()
        pipe.hdel("applications", app_id)
        pipe.srem(f"projects:{app.project_id}:apps", app_id)
        pipe.delete(f"apps:{app_id}:deployments")
        await pipe.execute()
        log.info(f"application deleted: {app_id}")
        return True

    async def set_deployment(self, deploy: Deployment) -> None:
        now = int(time.time())
        if not deploy.started_at:
            deploy = Deployment(**{**msgspec.structs.asdict(deploy), "started_at": now})
        pipe = self.redis.pipeline()
        pipe.hset(f"apps:{deploy.app_id}:deployments", deploy.id, self.encoder.encode(deploy))
        pipe.zadd(f"apps:{deploy.app_id}:deployments:index", {deploy.id: deploy.version})
        await pipe.execute()
        log.info(f"deployment set: {deploy.id} v{deploy.version}")
    
    async def get_deployment(self, app_id: str, deploy_id: str) -> Deployment | None:
        data = await self.redis.hget(f"apps:{app_id}:deployments", deploy_id)
        return self._decode(data, Deployment)
    
    async def get_app_deployments(self, app_id: str, limit: int = 10) -> list[Deployment]:
        deploy_ids = await self.redis.zrevrange(f"apps:{app_id}:deployments:index", 0, limit - 1)
        if not deploy_ids:
            return []
        pipe = self.redis.pipeline()
        for did in deploy_ids:
            did_str = did.decode() if isinstance(did, bytes) else did
            pipe.hget(f"apps:{app_id}:deployments", did_str)
        results = await pipe.execute()
        return [self._decode(r, Deployment) for r in results if r]
    
    async def get_next_deployment_version(self, app_id: str) -> int:
        last = await self.redis.zrevrange(f"apps:{app_id}:deployments:index", 0, 0, withscores=True)
        if not last:
            return 1
        return int(last[0][1]) + 1

    async def set_git_repo(self, repo: GitRepo) -> None:
        now = int(time.time())
        if not repo.created_at:
            repo = GitRepo(**{**msgspec.structs.asdict(repo), "created_at": now})
        await self.redis.hset("git_repos", repo.id, self.encoder.encode(repo))
        log.info(f"git repo set: {repo.id}")
    
    async def get_git_repo(self, repo_id: str) -> GitRepo | None:
        data = await self.redis.hget("git_repos", repo_id)
        return self._decode(data, GitRepo)
    
    async def get_git_repo_by_url(self, url: str, branch: str) -> GitRepo | None:
        repos = await self.get_all_git_repos()
        for repo in repos:
            if repo.url == url and repo.branch == branch:
                return repo
        return None
    
    async def get_all_git_repos(self) -> list[GitRepo]:
        data = await self.redis.hgetall("git_repos")
        return [self._decode(v, GitRepo) for v in data.values()]
    
    async def delete_git_repo(self, repo_id: str) -> bool:
        result = await self.redis.hdel("git_repos", repo_id)
        if result:
            log.info(f"git repo deleted: {repo_id}")
        return bool(result)
    
    async def update_git_repo_commit(self, repo_id: str, commit: str) -> None:
        repo = await self.get_git_repo(repo_id)
        if repo:
            repo = GitRepo(**{**msgspec.structs.asdict(repo), "last_commit": commit, "last_deploy_at": int(time.time())})
            await self.redis.hset("git_repos", repo_id, self.encoder.encode(repo))

    async def set_secret(self, secret: Secret) -> None:
        now = int(time.time())
        if not secret.created_at:
            secret = Secret(**{**msgspec.structs.asdict(secret), "created_at": now})
        pipe = self.redis.pipeline()
        pipe.hset(f"secrets:{secret.project_id}", secret.name, self.encoder.encode(secret))
        await pipe.execute()
        log.info(f"secret set: {secret.name} in {secret.project_id}")
    
    async def get_secret(self, project_id: str, name: str) -> Secret | None:
        data = await self.redis.hget(f"secrets:{project_id}", name)
        return self._decode(data, Secret)
    
    async def get_project_secrets(self, project_id: str) -> list[Secret]:
        data = await self.redis.hgetall(f"secrets:{project_id}")
        return [self._decode(v, Secret) for v in data.values()]
    
    async def delete_secret(self, project_id: str, name: str) -> bool:
        result = await self.redis.hdel(f"secrets:{project_id}", name)
        return bool(result)
