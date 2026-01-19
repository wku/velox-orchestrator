from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(title="Demo API")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/")
def root():
    return {"service": "demo-api", "version": os.getenv("APP_VERSION", "1.0.0")}

@app.get("/health")
def health():
    return {"healthy": True}

@app.get("/users")
def users():
    return [{"id": 1, "name": "Anna Lindberg"}, {"id": 2, "name": "Erik Johansson"}]

@app.get("/products")
def products():
    return [{"id": 1, "name": "Nordic Coffee", "price": 12.50}, {"id": 2, "name": "Swedish Bread", "price": 8.00}]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
