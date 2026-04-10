"""
FastAPI dependency injection for shared resources.
Using a module-level singleton for the VMService keeps us from
re-authenticating against Keystone on every request.
"""
from fastapi import Depends

from app.config import Settings, get_settings
from app.services.vm_service import VMService

# Module-level singleton — lru_cache doesn't work reliably with Depends
# because FastAPI dependency objects aren't hashable across all contexts.
_vm_service_instance: VMService | None = None


def get_vm_service(settings: Settings = Depends(get_settings)) -> VMService:
    global _vm_service_instance
    if _vm_service_instance is None:
        _vm_service_instance = VMService(settings)
    return _vm_service_instance
