from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import access_policies, activation_codes, agent, alarms, audit, auth, devices, frps_auth, site_access, sites, vendors, ws_remote, ws_vnc
from app.core.config import settings
from app.core.database import engine, Base

# Import all models so Base.metadata.create_all registers them
import app.models.tenant  # noqa: F401
import app.models.user  # noqa: F401
import app.models.site  # noqa: F401
import app.models.device  # noqa: F401
import app.models.audit  # noqa: F401
import app.models.claim  # noqa: F401
import app.models.alarm  # noqa: F401
import app.models.invite  # noqa: F401
import app.models.access_policy  # noqa: F401
import app.models.user_site_access  # noqa: F401
import app.models.activation_code  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    from app.services.heartbeat import heartbeat_checker_loop
    from app.vendors.registry import init_default_adapters

    # Create tables on startup (dev only; use Alembic migrations in prod)
    if settings.environment == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # Initialize vendor adapter registry
    init_default_adapters()

    # Start background heartbeat checker
    heartbeat_task = asyncio.create_task(heartbeat_checker_loop())

    yield

    # Shutdown: cancel background tasks
    heartbeat_task.cancel()
    try:
        await heartbeat_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(devices.router)
app.include_router(sites.router)
app.include_router(agent.router)
app.include_router(audit.router)
app.include_router(vendors.router)
app.include_router(ws_remote.router)
app.include_router(alarms.router)
app.include_router(access_policies.router)
app.include_router(site_access.router)
app.include_router(frps_auth.router)
app.include_router(activation_codes.router)
app.include_router(ws_vnc.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.app_name}
