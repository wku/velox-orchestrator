import asyncio
import hashlib
import hmac
import logging
import time
import uuid
import yaml
from pathlib import Path
from src.core.registry import Registry, EventBus
from src.core.models import GitRepo, GitProvider, Project, Application, DeploySource, DeployStatus, Secret
from src import config

log = logging.getLogger(__name__)

class WebhookHandler:
    def __init__(self, registry: Registry, event_bus: EventBus):
        self.registry = registry
        self.event_bus = event_bus
        self.deploy_dir = Path(config.DEPLOY_PATH)
    
    def verify_github_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        if not signature or not secret:
            return not secret
        expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
    
    def verify_gitlab_token(self, token: str, secret: str) -> bool:
        if not secret:
            return True
        return token == secret
    
    async def handle_github(self, payload: dict, signature: str) -> dict:
        repo_url = payload.get("repository", {}).get("clone_url", "")
        ref = payload.get("ref", "")
        branch = ref.replace("refs/heads/", "") if ref.startswith("refs/heads/") else ""
        commit = payload.get("after", "")
        if not repo_url or not branch:
            return {"status": "ignored", "reason": "missing repo or branch"}
        repo = await self.registry.get_git_repo_by_url(repo_url, branch)
        if not repo:
            repo_url_ssh = payload.get("repository", {}).get("ssh_url", "")
            repo = await self.registry.get_git_repo_by_url(repo_url_ssh, branch)
        if not repo:
            return {"status": "ignored", "reason": "repo not registered"}
        if not repo.enabled:
            return {"status": "ignored", "reason": "repo disabled"}
        if not self.verify_github_signature(str(payload).encode(), signature, repo.webhook_secret):
            return {"status": "error", "reason": "invalid signature"}
        return await self._trigger_deploy(repo, commit)
    
    async def handle_gitlab(self, payload: dict, token: str) -> dict:
        repo_url = payload.get("repository", {}).get("git_http_url", "")
        ref = payload.get("ref", "")
        branch = ref.replace("refs/heads/", "") if ref.startswith("refs/heads/") else ""
        commit = payload.get("checkout_sha", "") or payload.get("after", "")
        if not repo_url or not branch:
            return {"status": "ignored", "reason": "missing repo or branch"}
        repo = await self.registry.get_git_repo_by_url(repo_url, branch)
        if not repo:
            return {"status": "ignored", "reason": "repo not registered"}
        if not repo.enabled:
            return {"status": "ignored", "reason": "repo disabled"}
        if not self.verify_gitlab_token(token, repo.webhook_secret):
            return {"status": "error", "reason": "invalid token"}
        return await self._trigger_deploy(repo, commit)
    
    async def handle_gitea(self, payload: dict, signature: str) -> dict:
        repo_url = payload.get("repository", {}).get("clone_url", "")
        ref = payload.get("ref", "")
        branch = ref.replace("refs/heads/", "") if ref.startswith("refs/heads/") else ""
        commit = payload.get("after", "")
        if not repo_url or not branch:
            return {"status": "ignored", "reason": "missing repo or branch"}
        repo = await self.registry.get_git_repo_by_url(repo_url, branch)
        if not repo:
            return {"status": "ignored", "reason": "repo not registered"}
        if not repo.enabled:
            return {"status": "ignored", "reason": "repo disabled"}
        return await self._trigger_deploy(repo, commit)
    
    async def _trigger_deploy(self, repo: GitRepo, commit: str) -> dict:
        if repo.last_commit == commit:
            return {"status": "ignored", "reason": "same commit"}
        log.info(f"webhook triggered deploy: {repo.url} branch={repo.branch} commit={commit[:8]}")
        await self.registry.update_git_repo_commit(repo.id, commit)
        await self.event_bus.emit("webhook_received", {"repo_id": repo.id, "commit": commit})
        return {"status": "accepted", "repo_id": repo.id, "commit": commit}
    
    async def clone_and_parse_config(self, repo: GitRepo) -> dict | None:
        repo_dir = self.deploy_dir / f"repo-{repo.id}"
        if repo_dir.exists():
            import shutil
            shutil.rmtree(repo_dir)
        proc = await asyncio.create_subprocess_exec(
            "git", "clone", "--depth", "1", "--branch", repo.branch, repo.url, str(repo_dir),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            log.error(f"git clone failed: {stderr.decode()}")
            return None
        config_path = repo_dir / "deploy.yaml"
        compose_path = repo_dir / "docker-compose.yml"
        
        if not config_path.exists():
            log.error(f"deploy.yaml not found: {config_path}")
            return None
        if not compose_path.exists():
            log.error(f"docker-compose.yml not found: {compose_path}")
            return None
            
        with open(config_path) as f:
            deploy_config = yaml.safe_load(f)
        with open(compose_path) as f:
            compose_config = yaml.safe_load(f)
            
        return {
            "_repo_dir": str(repo_dir),
            "_repo_id": repo.id,
            "deploy_config": deploy_config,
            "compose_config": compose_config
        }
    
    async def resolve_secrets(self, project_id: str, env: dict) -> dict:
        resolved = {}
        secrets = await self.registry.get_project_secrets(project_id)
        secrets_map = {s.name: s.value for s in secrets}
        for key, value in env.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                secret_name = value[2:-1]
                resolved[key] = secrets_map.get(secret_name, value)
            else:
                resolved[key] = value
        return resolved
