"""
Entry point for the OpenStack VM Lifecycle API.

Design decisions:
- FastAPI for async-ready, auto-documented REST APIs
- openstack SDK (openstacksdk) for all Nova/Keystone calls
- Pydantic v2 for request/response validation
- Structured logging (JSON in prod, human-readable in dev)
"""
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.exceptions import (
    VMNotFoundError,
    VMOperationError,
    OpenStackConnectionError,
    vm_not_found_handler,
    vm_operation_error_handler,
    openstack_connection_error_handler,
)
from app.routers import health, vms

settings = get_settings()

# ------------------------------------------------------------------
# Logging setup
# ------------------------------------------------------------------
log_format = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format=log_format,
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# App lifecycle
# ------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting OpenStack VM Lifecycle API (env=%s)", settings.app_env)
    yield
    logger.info("Shutting down")


# ------------------------------------------------------------------
# App factory
# ------------------------------------------------------------------
app = FastAPI(
    title="OpenStack VM Lifecycle API",
    description=(
        "REST API for managing OpenStack VM lifecycle operations — "
        "provisioning, power management, and console access."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS — tighten origins in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_env == "development" else [],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------
# Exception handlers
# ------------------------------------------------------------------
app.add_exception_handler(VMNotFoundError, vm_not_found_handler)
app.add_exception_handler(VMOperationError, vm_operation_error_handler)
app.add_exception_handler(OpenStackConnectionError, openstack_connection_error_handler)

# ------------------------------------------------------------------
# Routers
# ------------------------------------------------------------------
app.include_router(health.router)
app.include_router(vms.router, prefix=settings.api_prefix)
