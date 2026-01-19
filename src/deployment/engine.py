import asyncio
import logging
import os
import shutil
import tempfile
import time
import uuid
import aiodocker
import yaml
from pathlib import Path
from src.core.registry import Registry, EventBus
from src.core.models import Application, Deployment, DeploySource, DeployStatus, Route, Upstream, Protocol, Project, GitRepo
from src import config

log = logging.getLogger(__name__)

class DeploymentEngine:
    def __init__(self, registry: Registry, event_bus: EventBus):
        self.registry = registry
        self.event_bus = event_bus
        self.docker: aiodocker.Docker | None = None
        self.deploy_dir = Path(config.DEPLOY_PATH)
        self._tasks: dict[str, asyncio.Task] = {}
        self._container_ips: dict[str, str] = {}
    
    async def start(self) -> None:
        self.docker = aiodocker.Docker()
        self.deploy_dir.mkdir(parents=True, exist_ok=True)
        self.event_bus.on("webhook_received", self._on_webhook)
        log.info("deployment engine started")
    
    async def stop(self) -> None:
        for task in self._tasks.values():
            task.cancel()
        if self.docker:
            await self.docker.close()

    async def _on_webhook(self, data: dict) -> None:
        repo_id = data.get("repo_id")
        if not repo_id:
            return
        repo = await self.registry.get_git_repo(repo_id)
        if not repo:
            return
        asyncio.create_task(self.deploy_from_repo(repo))

    async def deploy_from_repo(self, repo: GitRepo) -> list[Application]:
        from src.webhook.handler import WebhookHandler
        handler = WebhookHandler(self.registry, self.event_bus)
        cfg = await handler.clone_and_parse_config(repo)
        if not cfg:
            log.error(f"failed to parse config from repo: {repo.id}")
            return []
        return await self.deploy_from_config(cfg, repo)

    async def deploy_from_config(self, cfg: dict, repo: GitRepo | None = None) -> list[Application]:
        repo_dir = cfg.get("_repo_dir", "")
        deploy_config = cfg.get("deploy_config", {})
        compose_config = cfg.get("compose_config", {})
        
        if not deploy_config or not compose_config:
            log.error("missing deploy_config or compose_config")
            return []

        project_id = deploy_config.get("id")
        project_name = deploy_config.get("name", project_id)
        
        if not project_id:
            log.error("project id is required")
            return []
            
        project = Project(
            id=project_id,
            name=deploy_config.get("name", project_id),
            description=deploy_config.get("description", ""),
            source_path=repo_dir, # Store local path if available
            env=deploy_config.get("env", {})
        )
        await self.registry.set_project(project)
        
        if repo and not repo.project_id:
            import msgspec
            repo = GitRepo(**{**msgspec.structs.asdict(repo), "project_id": project_id})
            await self.registry.set_git_repo(repo)

        compose_services = compose_config.get("services", {})
        deploy_services = deploy_config.get("services", {})
        
        apps = await self._build_apps(project_id, compose_services, deploy_services, repo_dir)
        deploy_order = self._resolve_deploy_order(apps)
        
        log.info(f"deploy order: {[a.id for a in deploy_order]}")
        
        deployed = []
        for app in deploy_order:
            await self.registry.set_application(app)
            await self.deploy(app)
            # Note: Dependency waiting is now handled inside deploy via healthchecks
            deployed.append(app)
        return deployed

    async def _build_apps(self, project_id: str, compose_services: dict, deploy_services: dict, repo_dir: str) -> list[Application]:
        apps = []
        for svc_name, svc_def in compose_services.items():
            # Base info from docker-compose
            image = svc_def.get("image", "")
            build_def = svc_def.get("build")
            
            source = DeploySource.IMAGE
            source_url = ""
            dockerfile = "Dockerfile"
            build_context = "."
            
            if build_def:
                source = DeploySource.GIT
                source_url = repo_dir
                if isinstance(build_def, str):
                    build_context = build_def
                elif isinstance(build_def, dict):
                    build_context = build_def.get("context", ".")
                    dockerfile = build_def.get("dockerfile", "Dockerfile")
            
            # Metadata from deploy.yaml
            deploy_meta = deploy_services.get(svc_name, {})
            
            # Environment merging
            env = svc_def.get("environment", {})
            if isinstance(env, list):
                # Handle list format ["KEY=VAL", ...]
                env_dict = {}
                for item in env:
                    if "=" in item:
                        k, v = item.split("=", 1)
                        env_dict[k] = v
                env = env_dict
            
            # Healthcheck parsing
            healthcheck = svc_def.get("healthcheck")
            # Convert list syntax to string if needed
            if healthcheck and isinstance(healthcheck.get("test"), list):
                 # Keep it as list for aiodocker exec
                 pass

            # Domain logic: Default to {svc}-{project}.{IP}.nip.io if not set
            domain = deploy_meta.get("domain", "")
            if not domain:
                 # Try config.LOCAL_IP (127.0.0.1)
                 local_ip = config.LOCAL_IP
                 domain = f"{svc_name}-{project_id}.{local_ip}.nip.io"

            app = Application(
                id=f"{project_id}-{svc_name}", # Unique ID including project
                project_id=project_id,
                name=svc_name,
                source=source,
                source_url=source_url,
                dockerfile=dockerfile,
                build_context=build_context,
                image=image,
                domain=domain,
                port=deploy_meta.get("port", 80), 
                env=env,
                volumes=svc_def.get("volumes", []),
                networks=svc_def.get("networks", [config.PROXY_NETWORK]),
                replicas=deploy_meta.get("replicas", 1),
                depends_on=[f"{project_id}-{dep}" for dep in svc_def.get("depends_on", [])],
                healthcheck=healthcheck,
            )
            
            # Port auto-detection from compose if not in deploy
            if not app.domain and "ports" in svc_def:
                # If ports defined but no domain, maybe we don't route? 
                # Or we try to grab the internal port.
                # ports: ["8080:80"] -> internal is 80
                pass

            apps.append(app)
        return apps

    def _resolve_deploy_order(self, apps: list[Application]) -> list[Application]:
        app_map = {a.id: a for a in apps}
        visited = set()
        order = []
        def visit(app_id: str):
            if app_id in visited:
                return
            visited.add(app_id)
            app = app_map.get(app_id)
            if not app:
                return
            for dep in app.depends_on:
                visit(dep)
            order.append(app)
        for app in apps:
            visit(app.id)
        return order

    async def _wait_for_healthy(self, app: Application, container_ids: list[str], timeout: int = 60) -> bool:
        if not app.healthcheck or not container_ids:
            await asyncio.sleep(2)
            return True
        check = app.healthcheck
        test = check.get("test", "")
        interval = check.get("interval", 5)
        if isinstance(interval, str):
            interval = int(interval.rstrip("s"))
        
        start = time.time()
        while time.time() - start < timeout:
            results = await asyncio.gather(*[self._run_healthcheck(cid, test) for cid in container_ids])
            if all(results):
                log.info(f"all services healthy: {app.id}")
                return True
            await asyncio.sleep(interval)
        log.warning(f"healthcheck timeout: {app.id}")
        return False

    async def _run_healthcheck(self, container_id: str, test: str | list) -> bool:
        try:
            container = await self.docker.containers.get(container_id)
            cmd = test
            if isinstance(test, str):
                # If string using shell
                cmd = ["sh", "-c", test]
            elif isinstance(test, list):
                 # docker-compose uses ["CMD", "curl", ...] or ["CMD-SHELL", "..."]
                 if test[0] in ["CMD", "CMD-SHELL"]:
                     cmd = test[1:] if len(test) > 1 else test
                     if test[0] == "CMD-SHELL":
                         cmd = ["sh", "-c", " ".join(cmd)]
            
            log.info(f"Checking health {container_id} with cmd: {cmd}")
            # tty=True merges stdout and stderr so we capture everything
            exec_result = await container.exec(cmd=cmd, tty=True)
            async with exec_result.start() as stream:
                # Read output (stdout/stderr are often muxed here depending on detach)
                msg = await stream.read_out()
                output = msg or b""
            # Wait for process to finish
            for _ in range(10):
                inspect = await exec_result.inspect()
                if not inspect.get("Running"):
                    break
                await asyncio.sleep(0.2)
            
            code = inspect.get("ExitCode")
            if code is None:
                code = 1
                
            if code != 0:
                log.warning(f"healthcheck failed {container_id} code={code} output={output}")
            return code == 0
        except Exception as e:
            log.warning(f"healthcheck failed {container_id}: {e}")
            return False

    async def deploy(self, app: Application) -> Deployment:
        version = await self.registry.get_next_deployment_version(app.id)
        deploy = Deployment(id=f"{app.id}-v{version}", app_id=app.id, version=version, status=DeployStatus.PENDING)
        await self.registry.set_deployment(deploy)
        task = asyncio.create_task(self._run_deploy(app, deploy))
        self._tasks[deploy.id] = task
        return deploy

    async def _run_deploy(self, app: Application, deploy: Deployment) -> None:
        new_container_ids = []
        old_container_ids = app.container_ids
        try:
            deploy = Deployment(**{**self._to_dict(deploy), "status": DeployStatus.BUILDING})
            await self.registry.set_deployment(deploy)
            await self._update_app_status(app, DeployStatus.BUILDING)
            
            if app.source == DeploySource.GIT:
                image = await self._build_from_git(app, deploy)
            elif app.source == DeploySource.IMAGE:
                image = await self._pull_image(app, deploy)
            else:
                raise ValueError(f"unknown source: {app.source}")
            
            deploy = Deployment(**{**self._to_dict(deploy), "status": DeployStatus.DEPLOYING, "image": image})
            await self.registry.set_deployment(deploy)
            await self._update_app_status(app, DeployStatus.DEPLOYING)
            
            # Start NEW containers (old ones still running)
            # To avoid name conflicts, we might need unique names or relies on rolling update logic
            # Current _run_containers names: {app.id}-{i}
            # If we don't kill old, we can't reuse names unless we rename old ones first?
            # Or use randomized names?
            # Let's modify _run_containers to use unique names for new containers
            # Pass unique suffix? 
            # Or rename old ones? RENAME OLD is safer for seamless swap?
            # No, standard is usually: new containers get new unique names, and we rely on IP routing.
            # But we used fixed names for DNS.
            # If we want zero downtime, we can't have name conflict.
            # Fix: _run_containers should generate unique names like {app.id}-v{version}-{i}
            
            new_container_ids = await self._run_containers(app, image, deploy, suffix=f"v{deploy.version}")
            
            # Wait for health
            healthy = await self._wait_for_healthy(app, new_container_ids)
            
            if not healthy:
                raise RuntimeError("Healthcheck failed for new containers")
                
            # SWITCH TRAFFIC
            # Update app with NEW container IDs. Routes are generated from app.container_ids
            deploy = Deployment(**{**self._to_dict(deploy), "status": DeployStatus.RUNNING, "container_ids": new_container_ids, "finished_at": int(time.time())})
            await self.registry.set_deployment(deploy)
            
            app = Application(**{**self._to_dict(app), "status": DeployStatus.RUNNING, "container_ids": new_container_ids, "image": image})
            await self.registry.set_application(app)
            
            if app.domain:
                await self._create_route(app)
            
            await self.event_bus.emit("deploy_completed", {"app_id": app.id, "deploy_id": deploy.id})
            log.info(f"deploy completed: {deploy.id}")
            
            # Cleanup OLD containers
            await self._stop_containers(old_container_ids)
            
        except Exception as e:
            log.error(f"deploy failed {deploy.id}: {e}")
            deploy = Deployment(**{**self._to_dict(deploy), "status": DeployStatus.FAILED, "logs": str(e), "finished_at": int(time.time())})
            await self.registry.set_deployment(deploy)
            await self._update_app_status(app, DeployStatus.FAILED)
            
            # Cleanup NEW containers if they were started but failed
            if new_container_ids:
                for cid in new_container_ids:
                    try:
                        container = await self.docker.containers.get(cid)
                        logs = await container.log(stdout=True, stderr=True, tail=50)
                        log.error(f"container {cid} logs:\n{''.join(logs)}")
                    except Exception:
                        pass
                await self._stop_containers(new_container_ids)
                
            # Revert app status to running if old containers exist?
            # If we updated app.container_ids, we might have pointed to bad containers?
            # We updated app.container_ids ONLY after healthcheck passed.
            # So if exception happened before update, old are still there.
            
        finally:
            self._tasks.pop(deploy.id, None)

    async def _stop_containers(self, container_ids: list[str]) -> None:
        for cid in container_ids:
            try:
                container = await self.docker.containers.get(cid)
                await container.stop(t=5)
                await container.delete(force=True)
                log.info(f"cleaned up container: {cid}")
            except Exception as e:
                log.warning(f"failed to cleanup {cid}: {e}")

    async def _build_from_git(self, app: Application, deploy: Deployment) -> str:
        if app.source_url and Path(app.source_url).exists():
            repo_dir = Path(app.source_url)
        else:
            repo_dir = self.deploy_dir / app.id
            if repo_dir.exists():
                shutil.rmtree(repo_dir)
            proc = await asyncio.create_subprocess_exec(
                "git", "clone", "--depth", "1", "--branch", app.source_branch, app.source_url, str(repo_dir),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(f"git clone failed: {stderr.decode()}")
            log.info(f"git cloned: {app.source_url}")
        image_tag = f"vo/{app.id}:v{deploy.version}"
        build_context = repo_dir / app.build_context if app.build_context != "." else repo_dir
        dockerfile_path = build_context / app.dockerfile
        if not dockerfile_path.exists():
            dockerfile_path = await self._generate_dockerfile(build_context, app)
        with open(dockerfile_path, "rb") as f:
            dockerfile_content = f.read()
        tar_path = await self._create_build_tar(build_context, dockerfile_content)
        with open(tar_path, "rb") as tar_file:
            # Fix: when stream=True, it returns an async generator directly, don't await!
            async for chunk in self.docker.images.build(fileobj=tar_file, encoding="gzip", tag=image_tag, rm=True, stream=True):
                if "stream" in chunk:
                    log.debug(chunk["stream"].strip())
                if "error" in chunk:
                    raise RuntimeError(chunk["error"])
        os.unlink(tar_path)
        log.info(f"image built: {image_tag}")
        return image_tag

    async def _generate_dockerfile(self, context: Path, app: Application) -> Path:
        raise NotImplementedError("Auto-generation is disabled. Use docker-compose.yml and Dockerfile.")

    async def _create_build_tar(self, context: Path, dockerfile: bytes) -> str:
        import tarfile
        import io
        tar_path = tempfile.mktemp(suffix=".tar.gz")
        with tarfile.open(tar_path, "w:gz") as tar:
            for root, dirs, files in os.walk(context):
                dirs[:] = [d for d in dirs if d not in [".git", "node_modules", "__pycache__", ".venv"]]
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(context)
                    tar.add(file_path, arcname=arcname)
            df_info = tarfile.TarInfo(name="Dockerfile")
            df_info.size = len(dockerfile)
            tar.addfile(df_info, io.BytesIO(dockerfile))
        return tar_path

    async def _pull_image(self, app: Application, deploy: Deployment) -> str:
        image = app.image or app.source_url
        log.info(f"pulling image: {image}")
        try:
            await self.docker.images.pull(image)
        except aiodocker.exceptions.DockerError as e:
            # Check if image exists locally
            try:
                await self.docker.images.inspect(image)
                log.warning(f"pull failed ({e}), using local image: {image}")
                return image
            except Exception:
                pass
            raise e
        return image

    async def _run_containers(self, app: Application, image: str, deploy: Deployment, suffix: str = "") -> list[str]:
        project = await self.registry.get_project(app.project_id)
        env = {**(project.env if project else {}), **app.env}
        env = await self._resolve_service_refs(app, env)
        container_ids = []
        # Old container cleanup moved to _run_deploy to support zero-downtime
        networks = app.networks or [config.PROXY_NETWORK]
        for i in range(app.replicas):
            base_name = f"{app.id}-{suffix}" if suffix else app.id
            name = f"{base_name}-{i}" if app.replicas > 1 else base_name
            container_config = {
                "Image": image,
                "Env": [f"{k}={v}" for k, v in env.items()],
                "Labels": {
                    f"{config.LABEL_PREFIX}enable": "true",
                    f"{config.LABEL_PREFIX}app_id": app.id,
                    f"{config.LABEL_PREFIX}project_id": app.project_id,
                    f"{config.LABEL_PREFIX}deploy_id": deploy.id,
                },
                "Hostname": app.id,
            }
            
            # Domain generation logic
            # Start with configured domain
            domain = app.domain or ""
            
            if not domain:
                # Default: service-project.root_domain
                domain = f"{app.id}-{app.project_id}.{config.ROOT_DOMAIN}"
            elif "." not in domain:
                 # Short domain: domain.root_domain
                 domain = f"{domain}.{config.ROOT_DOMAIN}"

            # Only add labels if we have a valid domain
            if domain:
                container_config["Labels"][f"{config.LABEL_PREFIX}http.routers.{app.id}.host"] = domain
                container_config["Labels"][f"{config.LABEL_PREFIX}http.routers.{app.id}.port"] = str(app.port)
                
            if app.volumes:
                container_config["HostConfig"]["Binds"] = app.volumes
            container = await self.docker.containers.create(container_config, name=name)
            for net in networks:
                try:
                    network = await self.docker.networks.get(net)
                    await network.connect({"Container": container.id, "EndpointConfig": {"Aliases": [app.id]}})
                except aiodocker.exceptions.DockerError as e:
                    log.warning(f"network connect failed {net}: {e}")
            await container.start()
            cid = container.id[:12]
            container_ids.append(cid)
            info = await container.show()
            log.info(f"container started: {name} id={cid}")
            
            # Resolve IP: prefer app.networks (which includes proxy network)
            # Find the first IP associated with one of the desired networks
            found_ip = None
            container_networks = info.get("NetworkSettings", {}).get("Networks", {})
            
            # Check preferred networks first
            for net in networks:
                if net in container_networks and container_networks[net].get("IPAddress"):
                    found_ip = container_networks[net]["IPAddress"]
                    break
            
            # Fallback to any IP if not found
            if not found_ip:
                for net_info in container_networks.values():
                    if net_info.get("IPAddress"):
                        found_ip = net_info["IPAddress"]
                        break
            
            if found_ip:
                self._container_ips[app.id] = found_ip
        return container_ids

    async def _resolve_service_refs(self, app: Application, env: dict) -> dict:
        resolved = {}
        for key, value in env.items():
            if isinstance(value, str):
                for dep_id in app.depends_on:
                    if dep_id in value:
                        dep_app = await self.registry.get_application(dep_id)
                        if dep_app and dep_app.container_ids:
                            ip = self._container_ips.get(dep_id, dep_id)
                            value = value.replace(f"@{dep_id}", ip).replace(dep_id, dep_id)
            resolved[key] = value
        return resolved

    async def _create_route(self, app: Application) -> None:
        if not app.container_ids:
            return
        upstreams = []
        for cid in app.container_ids:
            try:
                container = await self.docker.containers.get(cid)
                info = await container.show()
                networks = info.get("NetworkSettings", {}).get("Networks", {})
                found_ip = None
                
                # Check PROXY_NETWORK first
                if config.PROXY_NETWORK in networks and networks[config.PROXY_NETWORK].get("IPAddress"):
                    found_ip = networks[config.PROXY_NETWORK]["IPAddress"]
                
                if not found_ip and app.networks:
                    for net in app.networks:
                        if net in networks and networks[net].get("IPAddress"):
                            found_ip = networks[net]["IPAddress"]
                            break

                if not found_ip:
                    for net_info in networks.values():
                        if net_info.get("IPAddress"):
                            found_ip = net_info["IPAddress"]
                            break
                            
                if found_ip:
                    upstreams.append(Upstream(address=found_ip, port=app.port, container_id=cid))
            except aiodocker.exceptions.DockerError:
                pass
        if not upstreams:
            log.warning(f"no upstreams for route: {app.id}")
            return
        route = Route(id=f"app-{app.id}", host=app.domain, upstreams=upstreams, protocol=Protocol.HTTP)
        await self.registry.set_route(route)
        log.info(f"route created: {app.domain} -> {len(upstreams)} upstreams")

    async def _update_app_status(self, app: Application, status: DeployStatus) -> None:
        app = Application(**{**self._to_dict(app), "status": status})
        await self.registry.set_application(app)

    async def stop_app(self, app: Application) -> None:
        for cid in app.container_ids:
            try:
                container = await self.docker.containers.get(cid)
                await container.stop(t=10)
                log.info(f"container stopped: {cid}")
            except aiodocker.exceptions.DockerError as e:
                log.warning(f"stop failed {cid}: {e}")
        await self._update_app_status(app, DeployStatus.STOPPED)

    async def remove_app(self, app: Application) -> None:
        for cid in app.container_ids:
            try:
                container = await self.docker.containers.get(cid)
                await container.stop(t=5)
                await container.delete()
            except aiodocker.exceptions.DockerError:
                pass
        if app.domain:
            await self.registry.delete_route(f"app-{app.id}")
        self._container_ips.pop(app.id, None)

    async def rollback(self, app: Application, target_version: int) -> Deployment | None:
        deployments = await self.registry.get_app_deployments(app.id)
        target = None
        for d in deployments:
            if d.version == target_version:
                target = d
                break
        if not target or not target.image:
            log.error(f"rollback target not found: v{target_version}")
            return None
        new_version = await self.registry.get_next_deployment_version(app.id)
        deploy = Deployment(id=f"{app.id}-v{new_version}", app_id=app.id, version=new_version, status=DeployStatus.DEPLOYING, image=target.image)
        await self.registry.set_deployment(deploy)
        container_ids = await self._run_containers(app, target.image, deploy)
        deploy = Deployment(**{**self._to_dict(deploy), "status": DeployStatus.RUNNING, "container_ids": container_ids, "finished_at": int(time.time())})
        await self.registry.set_deployment(deploy)
        app = Application(**{**self._to_dict(app), "status": DeployStatus.RUNNING, "container_ids": container_ids, "image": target.image})
        await self.registry.set_application(app)
        log.info(f"rollback completed: {app.id} to v{target_version}")
        return deploy

    def _to_dict(self, obj):
        import msgspec
        return msgspec.structs.asdict(obj)
