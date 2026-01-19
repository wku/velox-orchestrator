import logging
import aiodocker
from src.core.registry import Registry
from src.core.models import DockerNetwork, DockerContainer

log = logging.getLogger(__name__)

class DockerManager:
    def __init__(self, registry: Registry):
        self.registry = registry
        self.docker: aiodocker.Docker | None = None
    
    async def start(self) -> None:
        self.docker = aiodocker.Docker()
        await self._sync_networks()
        log.info("docker manager started")
    
    async def stop(self) -> None:
        if self.docker:
            await self.docker.close()
    
    async def _sync_networks(self) -> None:
        networks = await self.docker.networks.list()
        for net in networks:
            try:
                network = await self.docker.networks.get(net["Id"])
                info = await network.show()
                await self._store_network(info)
            except aiodocker.exceptions.DockerError:
                pass
    
    async def _store_network(self, info: dict) -> DockerNetwork:
        ipam_config = info.get("IPAM", {}).get("Config") or [{}]
        ipam = ipam_config[0] if ipam_config else {}
        containers = list(info.get("Containers", {}).keys())
        network = DockerNetwork(
            id=info["Id"][:12],
            name=info["Name"],
            driver=info.get("Driver", "bridge"),
            scope=info.get("Scope", "local"),
            subnet=ipam.get("Subnet"),
            gateway=ipam.get("Gateway"),
            containers=[c[:12] for c in containers]
        )
        await self.registry.set_network(network)
        return network
    
    async def list_networks(self) -> list[DockerNetwork]:
        return await self.registry.get_all_networks()
    
    async def get_network(self, network_id: str) -> DockerNetwork | None:
        return await self.registry.get_network(network_id)
    
    async def create_network(
        self,
        name: str,
        driver: str = "bridge",
        subnet: str | None = None,
        gateway: str | None = None,
        internal: bool = False
    ) -> DockerNetwork:
        net_config = {"Name": name, "Driver": driver, "Internal": internal}
        if subnet:
            ipam_config = [{"Subnet": subnet}]
            if gateway:
                ipam_config[0]["Gateway"] = gateway
            net_config["IPAM"] = {"Config": ipam_config}
        network = await self.docker.networks.create(net_config)
        info = await network.show()
        result = await self._store_network(info)
        log.info(f"network created: {name}")
        return result
    
    async def delete_network(self, network_id: str) -> bool:
        try:
            network = await self.docker.networks.get(network_id)
            await network.delete()
            await self.registry.delete_network(network_id[:12])
            log.info(f"network deleted: {network_id}")
            return True
        except aiodocker.exceptions.DockerError as e:
            log.error(f"network delete failed: {e}")
            return False
    
    async def connect_container(self, network_id: str, container_id: str) -> bool:
        try:
            network = await self.docker.networks.get(network_id)
            await network.connect({"Container": container_id})
            info = await network.show()
            await self._store_network(info)
            log.info(f"container {container_id[:12]} connected to {network_id[:12]}")
            return True
        except aiodocker.exceptions.DockerError as e:
            log.error(f"connect failed: {e}")
            return False
    
    async def disconnect_container(self, network_id: str, container_id: str) -> bool:
        try:
            network = await self.docker.networks.get(network_id)
            await network.disconnect({"Container": container_id})
            info = await network.show()
            await self._store_network(info)
            log.info(f"container {container_id[:12]} disconnected from {network_id[:12]}")
            return True
        except aiodocker.exceptions.DockerError as e:
            log.error(f"disconnect failed: {e}")
            return False
    
    async def list_containers(self, all_containers: bool = False) -> list[DockerContainer]:
        return await self.registry.get_all_containers()
    
    async def get_container(self, container_id: str) -> DockerContainer | None:
        return await self.registry.get_container(container_id)
    
    async def start_container(self, container_id: str) -> bool:
        try:
            container = await self.docker.containers.get(container_id)
            await container.start()
            log.info(f"container started: {container_id}")
            return True
        except aiodocker.exceptions.DockerError as e:
            log.error(f"start failed: {e}")
            return False
    
    async def stop_container(self, container_id: str, timeout: int = 10) -> bool:
        try:
            container = await self.docker.containers.get(container_id)
            await container.stop(t=timeout)
            log.info(f"container stopped: {container_id}")
            return True
        except aiodocker.exceptions.DockerError as e:
            log.error(f"stop failed: {e}")
            return False
    
    async def restart_container(self, container_id: str) -> bool:
        try:
            container = await self.docker.containers.get(container_id)
            await container.restart()
            log.info(f"container restarted: {container_id}")
            return True
        except aiodocker.exceptions.DockerError as e:
            log.error(f"restart failed: {e}")
            return False
    
    async def get_container_logs(self, container_id: str, tail: int = 100) -> str:
        try:
            container = await self.docker.containers.get(container_id)
            logs = await container.log(stdout=True, stderr=True, tail=tail)
            return "".join(logs)
        except aiodocker.exceptions.DockerError as e:
            log.error(f"get logs failed: {e}")
            return ""

    async def get_app_container_ids(self, app_id: str) -> list[str]:
        app = await self.registry.get_application(app_id)
        if not app:
            return []
        return app.container_ids
