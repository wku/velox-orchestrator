import asyncio
import logging
import aiodocker
from src.core.registry import Registry, EventBus
from src.core.models import Route, Upstream, Protocol, DockerContainer
from src import config

log = logging.getLogger(__name__)

class DockerProvider:
    def __init__(self, registry: Registry, event_bus: EventBus):
        self.registry = registry
        self.event_bus = event_bus
        self.docker: aiodocker.Docker | None = None
        self.running = False
        self._watch_task: asyncio.Task | None = None
    
    async def start(self) -> None:
        self.docker = aiodocker.Docker()
        self.running = True
        await self.sync_all()
        self._watch_task = asyncio.create_task(self._watch_events())
        log.info("docker provider started")
    
    async def stop(self) -> None:
        self.running = False
        if self._watch_task:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
        if self.docker:
            await self.docker.close()
        log.info("docker provider stopped")
    
    async def sync_all(self) -> None:
        containers = await self.docker.containers.list()
        for container in containers:
            await self._process_container(container, "start")
        log.info(f"synced {len(containers)} containers")
    
    async def _watch_events(self) -> None:
        subscriber = self.docker.events.subscribe()
        while self.running:
            try:
                event = await subscriber.get()
                if not event:
                    continue
                if event.get("Type") != "container":
                    continue
                action = event.get("Action", "")
                if action not in ("start", "stop", "die", "kill"):
                    continue
                container_id = event.get("Actor", {}).get("ID", "")
                if not container_id:
                    continue
                if action == "start":
                    try:
                        container = await self.docker.containers.get(container_id)
                        await self._process_container(container, action)
                    except aiodocker.exceptions.DockerError as e:
                        log.warning(f"container get failed {container_id}: {e}")
                else:
                    await self._remove_container_routes(container_id[:12])
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"docker event error: {e}")
                await asyncio.sleep(1)
    
    async def _process_container(self, container, action: str) -> None:
        try:
            info = await container.show()
        except aiodocker.exceptions.DockerError:
            return
        labels = info.get("Config", {}).get("Labels") or {}
        container_id = info["Id"][:12]
        container_name = info.get("Name", "").lstrip("/")
        if action in ("stop", "die", "kill"):
            await self._remove_container_routes(container_id)
            await self.registry.delete_container(container_id)
            return
        networks = info.get("NetworkSettings", {}).get("Networks") or {}
        ip_addresses = {}
        for net_name, net_info in networks.items():
            if net_info.get("IPAddress"):
                ip_addresses[net_name] = net_info["IPAddress"]
        docker_container = DockerContainer(
            id=container_id,
            name=container_name,
            image=info.get("Config", {}).get("Image", ""),
            status=info.get("State", {}).get("Status", ""),
            labels=labels,
            networks=list(networks.keys()),
            ip_addresses=ip_addresses
        )
        await self.registry.set_container(docker_container)
        if labels.get(f"{config.LABEL_PREFIX}enable") != "true":
            return
        routes = self._parse_labels(labels, container_id, ip_addresses)
        for route in routes:
            await self.registry.set_route(route)
        await self.event_bus.emit("routes_updated", {"container_id": container_id, "routes": len(routes)})
    
    def _parse_labels(self, labels: dict, container_id: str, ip_addresses: dict) -> list[Route]:
        if not ip_addresses:
            log.warning(f"container {container_id} has no ip address")
            return []
        
        ip_address = ip_addresses.get(config.PROXY_NETWORK)
        if not ip_address:
            ip_address = list(ip_addresses.values())[0]
        routes = []
        routers: dict[str, dict] = {}
        prefix = f"{config.LABEL_PREFIX}http.routers."
        for key, value in labels.items():
            if not key.startswith(prefix):
                continue
            rest = key[len(prefix):]
            parts = rest.split(".", 1)
            if len(parts) < 2:
                continue
            router_name, prop = parts[0], parts[1]
            if router_name not in routers:
                routers[router_name] = {}
            routers[router_name][prop] = value
        for router_name, props in routers.items():
            host = props.get("host", "").strip("`").strip()
            if not host:
                continue
            port = int(props.get("port", 80))
            path = props.get("path", "/")
            tls = props.get("tls", "").lower() == "true"
            middlewares = []
            if props.get("middlewares"):
                middlewares = [m.strip() for m in props["middlewares"].split(",") if m.strip()]
            route = Route(
                id=f"{container_id}-{router_name}",
                host=host,
                path=path,
                protocol=Protocol.HTTPS if tls else Protocol.HTTP,
                upstreams=[Upstream(address=ip_address, port=port, container_id=container_id)],
                middlewares=middlewares,
                strip_path=props.get("strip_path", "").lower() == "true",
                preserve_host=props.get("preserve_host", "true").lower() != "false"
            )
            routes.append(route)
            log.info(f"route parsed: {route.host}{route.path} -> {ip_address}:{port}")
        return routes
    
    async def _remove_container_routes(self, container_id: str) -> None:
        routes = await self.registry.get_all_routes()
        for route in routes:
            if route.id.startswith(f"{container_id}-"):
                await self.registry.delete_route(route.id)
        await self.event_bus.emit("routes_updated", {"container_id": container_id, "removed": True})
