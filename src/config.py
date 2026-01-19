import os

REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
REDIS_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}" if REDIS_PASSWORD else f"redis://{REDIS_HOST}:{REDIS_PORT}"
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://vo:Bz5r1bizzx4oChKZXZ6XU1@localhost/vo")

DOCKER_SOCKET = os.getenv("DOCKER_SOCKET", "/var/run/docker.sock")

ACME_EMAIL = os.getenv("ACME_EMAIL", "admin@example.com")
ACME_STAGING = os.getenv("ACME_STAGING", "true").lower() == "true"
ACME_DIRECTORY_STAGING = "https://acme-staging-v02.api.letsencrypt.org/directory"
ACME_DIRECTORY_PROD = "https://acme-v02.api.letsencrypt.org/directory"

CERTS_PATH = os.getenv("CERTS_PATH", "/app/certs")
LABEL_PREFIX = os.getenv("LABEL_PREFIX", "vo.")

LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", 8000))

HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", 10))
CERT_RENEWAL_DAYS = int(os.getenv("CERT_RENEWAL_DAYS", 30))

WILDCARD_DOMAIN_SUFFIXES = [
    ".nip.io",
    ".sslip.io",
    ".lvh.me",
    ".localtest.me"
]
LOCAL_IP = os.getenv("LOCAL_IP", "127.0.0.1")
ROOT_DOMAIN = os.getenv("ROOT_DOMAIN", f"{LOCAL_IP}.nip.io")

DEPLOY_PATH = os.getenv("DEPLOY_PATH", "/app/deployments")
PROXY_NETWORK = os.getenv("PROXY_NETWORK", "vo-proxy")

AUTH_USER = os.getenv("AUTH_USER", "admin")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "admin")
SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key-change-me")
