import os
import asyncio
import logging
import time
import base64
import hashlib
import json
import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.x509.oid import NameOID
from src.core.registry import Registry
from src.core.models import Certificate
from src import config

log = logging.getLogger(__name__)

def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def b64url_decode(data: str) -> bytes:
    padding_needed = 4 - len(data) % 4
    if padding_needed != 4:
        data += "=" * padding_needed
    return base64.urlsafe_b64decode(data)

class ACMEClient:
    def __init__(self, registry: Registry):
        self.registry = registry
        self.directory_url = config.ACME_DIRECTORY_STAGING if config.ACME_STAGING else config.ACME_DIRECTORY_PROD
        self.email = config.ACME_EMAIL
        self.certs_path = config.CERTS_PATH
        self.account_key: rsa.RSAPrivateKey | None = None
        self.account_uri: str | None = None
        self.directory: dict = {}
        self.http = httpx.AsyncClient(timeout=30)
        self._nonce: str | None = None
    
    async def start(self) -> None:
        os.makedirs(self.certs_path, exist_ok=True)
        os.makedirs(os.path.join(self.certs_path, "accounts"), exist_ok=True)
        await self._load_or_create_account()
        log.info(f"acme client started (staging={config.ACME_STAGING})")
    
    async def stop(self) -> None:
        await self.http.aclose()
    
    async def _load_or_create_account(self) -> None:
        key_path = os.path.join(self.certs_path, "accounts", "account.key")
        if os.path.exists(key_path):
            with open(key_path, "rb") as f:
                self.account_key = serialization.load_pem_private_key(f.read(), password=None)
            log.info("account key loaded")
        else:
            self.account_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            with open(key_path, "wb") as f:
                f.write(self.account_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            log.info("account key created")
        resp = await self.http.get(self.directory_url)
        self.directory = resp.json()
        await self._register_account()
    
    async def _get_nonce(self) -> str:
        if self._nonce:
            nonce = self._nonce
            self._nonce = None
            return nonce
        resp = await self.http.head(self.directory["newNonce"])
        return resp.headers["Replay-Nonce"]
    
    def _jwk(self) -> dict:
        pub = self.account_key.public_key().public_numbers()
        return {
            "kty": "RSA",
            "n": b64url(pub.n.to_bytes((pub.n.bit_length() + 7) // 8, "big")),
            "e": b64url(pub.e.to_bytes((pub.e.bit_length() + 7) // 8, "big"))
        }
    
    def _thumbprint(self) -> str:
        jwk = self._jwk()
        jwk_json = json.dumps(jwk, sort_keys=True, separators=(",", ":"))
        return b64url(hashlib.sha256(jwk_json.encode()).digest())
    
    async def _signed_request(self, url: str, payload: dict | None) -> httpx.Response:
        nonce = await self._get_nonce()
        protected = {"alg": "RS256", "nonce": nonce, "url": url}
        if self.account_uri:
            protected["kid"] = self.account_uri
        else:
            protected["jwk"] = self._jwk()
        protected_b64 = b64url(json.dumps(protected).encode())
        if payload is None:
            payload_b64 = ""
        else:
            payload_b64 = b64url(json.dumps(payload).encode())
        signing_input = f"{protected_b64}.{payload_b64}".encode()
        signature = self.account_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
        jws = {"protected": protected_b64, "payload": payload_b64, "signature": b64url(signature)}
        resp = await self.http.post(url, json=jws, headers={"Content-Type": "application/jose+json"})
        if "Replay-Nonce" in resp.headers:
            self._nonce = resp.headers["Replay-Nonce"]
        return resp
    
    async def _register_account(self) -> None:
        payload = {"termsOfServiceAgreed": True, "contact": [f"mailto:{self.email}"]}
        resp = await self._signed_request(self.directory["newAccount"], payload)
        if resp.status_code in (200, 201):
            self.account_uri = resp.headers.get("Location")
            log.info(f"acme account registered: {self.account_uri}")
        else:
            log.error(f"account registration failed: {resp.text}")
    
    async def obtain_certificate(self, domain: str) -> Certificate | None:
        log.info(f"requesting certificate for {domain}")
        order_resp = await self._signed_request(
            self.directory["newOrder"],
            {"identifiers": [{"type": "dns", "value": domain}]}
        )
        if order_resp.status_code not in (200, 201):
            log.error(f"order failed: {order_resp.text}")
            return None
        order = order_resp.json()
        order_url = order_resp.headers.get("Location")
        for auth_url in order.get("authorizations", []):
            auth_resp = await self._signed_request(auth_url, None)
            auth = auth_resp.json()
            for challenge in auth.get("challenges", []):
                if challenge["type"] == "http-01":
                    if not await self._solve_http01(domain, challenge):
                        return None
                    break
        domain_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        csr = self._generate_csr(domain, domain_key)
        finalize_resp = await self._signed_request(order["finalize"], {"csr": csr})
        if finalize_resp.status_code not in (200, 201):
            log.error(f"finalize failed: {finalize_resp.text}")
            return None
        for _ in range(30):
            check_resp = await self._signed_request(order_url, None)
            status = check_resp.json().get("status")
            if status == "valid":
                order = check_resp.json()
                break
            if status == "invalid":
                log.error(f"order invalid: {check_resp.text}")
                return None
            await asyncio.sleep(2)
        else:
            log.error("order timeout")
            return None
        cert_resp = await self._signed_request(order["certificate"], None)
        if cert_resp.status_code != 200:
            log.error(f"cert download failed: {cert_resp.text}")
            return None
        cert_pem = cert_resp.text
        key_pem = domain_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        cert_path = os.path.join(self.certs_path, f"{domain}.crt")
        key_path = os.path.join(self.certs_path, f"{domain}.key")
        with open(cert_path, "w") as f:
            f.write(cert_pem)
        with open(key_path, "wb") as f:
            f.write(key_pem)
        cert_obj = x509.load_pem_x509_certificate(cert_pem.encode())
        expires_at = int(cert_obj.not_valid_after_utc.timestamp())
        certificate = Certificate(
            domain=domain,
            cert_path=cert_path,
            key_path=key_path,
            expires_at=expires_at
        )
        await self.registry.set_certificate(certificate)
        log.info(f"certificate obtained for {domain}, expires {cert_obj.not_valid_after_utc}")
        return certificate
    
    async def _solve_http01(self, domain: str, challenge: dict) -> bool:
        token = challenge["token"]
        key_auth = f"{token}.{self._thumbprint()}"
        await self.registry.set_acme_challenge(token, key_auth)
        log.info(f"challenge set for {domain}: {token}")
        resp = await self._signed_request(challenge["url"], {})
        if resp.status_code not in (200, 201):
            log.error(f"challenge notify failed: {resp.text}")
            await self.registry.delete_acme_challenge(token)
            return False
        for _ in range(30):
            await asyncio.sleep(2)
            check_resp = await self._signed_request(challenge["url"], None)
            status = check_resp.json().get("status")
            if status == "valid":
                log.info(f"challenge valid for {domain}")
                await self.registry.delete_acme_challenge(token)
                return True
            if status == "invalid":
                log.error(f"challenge invalid: {check_resp.text}")
                await self.registry.delete_acme_challenge(token)
                return False
        log.error("challenge timeout")
        await self.registry.delete_acme_challenge(token)
        return False
    
    def _generate_csr(self, domain: str, key: rsa.RSAPrivateKey) -> str:
        csr = x509.CertificateSigningRequestBuilder().subject_name(
            x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, domain)])
        ).sign(key, hashes.SHA256())
        return b64url(csr.public_bytes(serialization.Encoding.DER))
    
    async def renew_expiring(self, days_before: int = 30) -> list[Certificate]:
        threshold = int(time.time()) + (days_before * 86400)
        expiring = await self.registry.get_expiring_certificates(threshold)
        renewed = []
        for cert in expiring:
            if cert.auto_renew:
                log.info(f"renewing certificate for {cert.domain}")
                new_cert = await self.obtain_certificate(cert.domain)
                if new_cert:
                    renewed.append(new_cert)
        return renewed
