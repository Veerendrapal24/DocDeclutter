"""
DocDeclutter – FastAPI entry point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.router import api_router

app = FastAPI(
    title="DocDeclutter API",
    description="Metro Document Automation – FastAPI backend",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
# Allows local dev, any Vercel deployment (*.vercel.app), and custom domains from ALLOWED_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$|^https://[a-zA-Z0-9_\-\.]+\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "app": "DocDeclutter API", "version": "0.1.0"}


@app.get("/api/health", tags=["Health"])
def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import os
    import uvicorn

    server_port = int(os.environ.get("PORT", getattr(settings, "port", 8000)))
    uvicorn.run("app.main:app", host="0.0.0.0", port=server_port, reload=False)
