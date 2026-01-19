from sqlalchemy import Column, String, Integer, Boolean, Text, JSON, BigInteger, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from src.core.db import Base
import time

class ProjectModel(Base):
    __tablename__ = "projects"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(String, default="")
    source_path: Mapped[str] = mapped_column(String, default="")
    env: Mapped[dict] = mapped_column(JSON, default={})
    created_at: Mapped[int] = mapped_column(BigInteger, default=lambda: int(time.time()))
    updated_at: Mapped[int] = mapped_column(BigInteger, default=lambda: int(time.time()))

    applications = relationship("ApplicationModel", back_populates="project", cascade="all, delete-orphan")
    secrets = relationship("SecretModel", back_populates="project", cascade="all, delete-orphan")

class ApplicationModel(Base):
    __tablename__ = "applications"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String)
    
    # DeploySource enum stored as string
    source: Mapped[str] = mapped_column(String)
    source_url: Mapped[str] = mapped_column(String, default="")
    source_branch: Mapped[str] = mapped_column(String, default="main")
    dockerfile: Mapped[str] = mapped_column(String, default="Dockerfile")
    build_context: Mapped[str] = mapped_column(String, default=".")
    image: Mapped[str] = mapped_column(String, default="")
    compose_file: Mapped[str] = mapped_column(String, default="")
    
    domain: Mapped[str] = mapped_column(String, default="")
    port: Mapped[int] = mapped_column(Integer, default=80)
    env: Mapped[dict] = mapped_column(JSON, default={})
    volumes: Mapped[list[str]] = mapped_column(JSON, default=[])
    networks: Mapped[list[str]] = mapped_column(JSON, default=[])
    replicas: Mapped[int] = mapped_column(Integer, default=1)
    depends_on: Mapped[list[str]] = mapped_column(JSON, default=[])
    healthcheck: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
    status: Mapped[str] = mapped_column(String, default="pending")
    container_ids: Mapped[list[str]] = mapped_column(JSON, default=[])
    created_at: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=0)

    project = relationship("ProjectModel", back_populates="applications")

    # Add back_populates to deployments
    deployments = relationship("DeploymentModel", back_populates="application", cascade="all, delete-orphan")

class RouteModel(Base):
    __tablename__ = "routes"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    host: Mapped[str] = mapped_column(String, index=True)
    path: Mapped[str] = mapped_column(String, default="/")
    protocol: Mapped[str] = mapped_column(String, default="http")
    
    # Upstreams list[Upstream] stored as JSON
    upstreams: Mapped[list] = mapped_column(JSON, default=[])
    middlewares: Mapped[list[str]] = mapped_column(JSON, default=[])
    load_balancer: Mapped[str] = mapped_column(String, default="round_robin")
    health_check: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    strip_path: Mapped[bool] = mapped_column(Boolean, default=False)
    preserve_host: Mapped[bool] = mapped_column(Boolean, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

class DeploymentModel(Base):
    __tablename__ = "deployments"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    app_id: Mapped[str] = mapped_column(String, ForeignKey("applications.id"))
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String)
    image: Mapped[str] = mapped_column(String, default="")
    container_ids: Mapped[list[str]] = mapped_column(JSON, default=[])
    logs: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[int] = mapped_column(BigInteger, default=0)
    finished_at: Mapped[int] = mapped_column(BigInteger, default=0)

    application = relationship("ApplicationModel", back_populates="deployments")

class GitRepoModel(Base):
    __tablename__ = "git_repos"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    provider: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String, unique=True)
    branch: Mapped[str] = mapped_column(String, default="main")
    config_file: Mapped[str] = mapped_column(String, default="deploy.yaml")
    webhook_secret: Mapped[str] = mapped_column(String, default="")
    project_id: Mapped[str | None] = mapped_column(String, nullable=True)
    last_commit: Mapped[str] = mapped_column(String, default="")
    last_deploy_at: Mapped[int] = mapped_column(BigInteger, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[int] = mapped_column(BigInteger, default=0)

class SecretModel(Base):
    __tablename__ = "secrets"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String)
    value: Mapped[str] = mapped_column(String)
    created_at: Mapped[int] = mapped_column(BigInteger, default=0)

    project = relationship("ProjectModel", back_populates="secrets")

# Non-persistent or distinct models:
# Certificate, DockerNetwork, DockerContainer are usually ephemeral or synced from system, 
# but Certificates might need persistence. 
# For now, let's persist Certificates too just in case.

class CertificateModel(Base):
    __tablename__ = "certificates"
    
    domain: Mapped[str] = mapped_column(String, primary_key=True)
    cert_path: Mapped[str] = mapped_column(String)
    key_path: Mapped[str] = mapped_column(String)
    expires_at: Mapped[int] = mapped_column(BigInteger)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True)

class MiddlewareModel(Base):
    __tablename__ = "middlewares"
    
    name: Mapped[str] = mapped_column(String, primary_key=True)
    type: Mapped[str] = mapped_column(String)
    config: Mapped[dict] = mapped_column(JSON)
