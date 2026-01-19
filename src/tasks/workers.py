import asyncio
import logging
import httpx
from src.core.registry import Registry
from src.core.models import HealthCheckType
from src.acme.client import ACMEClient
from src import config

log = logging.getLogger(__name__)

class HealthChecker:
    def __init__(self, registry: Registry):
        self.registry = registry
        self.running = False
        self._task: asyncio.Task | None = None
        self.http = httpx.AsyncClient(timeout=5)
    
    async def start(self) -> None:
        self.running = True
        self._task = asyncio.create_task(self._run())
        log.info("health checker started")
    
    async def stop(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.http.aclose()
    
    async def _run(self) -> None:
        while self.running:
            try:
                await self._check_all()
            except Exception as e:
                log.error(f"health check error: {e}")
            await asyncio.sleep(config.HEALTH_CHECK_INTERVAL)
    
    async def _check_all(self) -> None:
        routes = await self.registry.get_all_routes()
        for route in routes:
            if not route.health_check or route.health_check.type == HealthCheckType.NONE:
                continue
            for upstream in route.upstreams:
                healthy = await self._check_upstream(route, upstream)
                await self.registry.update_upstream_health(
                    route.id, upstream.address, upstream.port, healthy
                )
    
    async def _check_upstream(self, route, upstream) -> bool:
        hc = route.health_check
        if hc.type == HealthCheckType.HTTP:
            url = f"http://{upstream.address}:{upstream.port}{hc.path}"
            try:
                resp = await self.http.get(url, timeout=hc.timeout)
                return resp.status_code < 500
            except Exception:
                return False
        elif hc.type == HealthCheckType.TCP:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(upstream.address, upstream.port),
                    timeout=hc.timeout
                )
                writer.close()
                await writer.wait_closed()
                return True
            except Exception:
                return False
        return True

class CertRenewalTask:
    def __init__(self, acme_client: ACMEClient):
        self.acme = acme_client
        self.running = False
        self._task: asyncio.Task | None = None
    
    async def start(self) -> None:
        self.running = True
        self._task = asyncio.create_task(self._run())
        log.info("cert renewal task started")
    
    async def stop(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _run(self) -> None:
        while self.running:
            try:
                renewed = await self.acme.renew_expiring(config.CERT_RENEWAL_DAYS)
                if renewed:
                    log.info(f"renewed {len(renewed)} certificates")
            except Exception as e:
                log.error(f"cert renewal error: {e}")
            await asyncio.sleep(3600)
