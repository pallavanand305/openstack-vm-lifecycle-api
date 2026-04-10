from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


class VMNotFoundError(Exception):
    def __init__(self, vm_id: str):
        self.vm_id = vm_id
        super().__init__(f"VM '{vm_id}' not found")


class VMOperationError(Exception):
    def __init__(self, message: str, vm_id: str = None):
        self.vm_id = vm_id
        super().__init__(message)


class OpenStackConnectionError(Exception):
    pass


async def vm_not_found_handler(request: Request, exc: VMNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc), "vm_id": exc.vm_id},
    )


async def vm_operation_error_handler(request: Request, exc: VMOperationError):
    logger.error("VM operation failed: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=409,
        content={"detail": str(exc)},
    )


async def openstack_connection_error_handler(request: Request, exc: OpenStackConnectionError):
    logger.critical("Cannot reach OpenStack: %s", exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "OpenStack service unavailable. Check connectivity and credentials."},
    )
