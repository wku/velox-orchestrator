import jwt
import datetime
import src.config as config
from litestar import Controller, post, get
from litestar.exceptions import NotAuthorizedException
from pydantic import BaseModel
from litestar.connection import Request

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

class AuthController(Controller):
    path = "/api/v1/auth"
    
    @post("/login")
    async def login(self, data: LoginRequest) -> TokenResponse:
        # Check against config
        if data.username != config.AUTH_USER or data.password != config.AUTH_PASSWORD:
            raise NotAuthorizedException("Invalid credentials")
            
        token = jwt.encode(
            {
                "sub": data.username,
                "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
            },
            config.SECRET_KEY,
            algorithm="HS256"
        )
        
        return TokenResponse(access_token=token, token_type="bearer")
    
    @get("/me")
    async def me(self, request: Request) -> dict:
        # Check if authenticated
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise NotAuthorizedException("Missing or invalid token")
            
        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, config.SECRET_KEY, algorithms=["HS256"])
            return {"status": "authenticated", "user": payload["sub"]}
        except jwt.ExpiredSignatureError:
            raise NotAuthorizedException("Token expired")
        except jwt.InvalidTokenError:
            raise NotAuthorizedException("Invalid token")
