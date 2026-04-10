"""
VM lifecycle router.

Endpoints follow REST conventions:
  GET    /vms          — list (paginated, filterable)
  POST   /vms          — provision a new VM
  GET    /vms/{id}     — get single VM
  DELETE /vms/{id}     — terminate VM
  POST   /vms/{id}/action   — lifecycle action (start/stop/reboot/etc.)
  GET    /vms/{id}/console  — get VNC/SPICE console URL
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query, status

from app.dependencies import get_vm_service
from app.services.vm_service import VMService
from app.schemas.vm import (
    VMCreateRequest,
    VMActionRequest,
    VMResponse,
    VMListResponse,
    VMConsoleResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/vms", tags=["vms"])


@router.get("", response_model=VMListResponse, summary="List VMs")
def list_vms(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by VM status (e.g. ACTIVE, STOPPED)"),
    svc: VMService = Depends(get_vm_service),
):
    items, total = svc.list_vms(page=page, page_size=page_size, status_filter=status_filter)
    return VMListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=VMResponse, status_code=status.HTTP_202_ACCEPTED, summary="Provision a VM")
def create_vm(
    payload: VMCreateRequest,
    svc: VMService = Depends(get_vm_service),
):
    """
    Kicks off VM provisioning. Returns 202 because OpenStack builds
    asynchronously — the VM will be in BUILD status initially.
    Poll GET /vms/{id} to track progress.
    """
    return svc.create_vm(
        name=payload.name,
        flavor_id=payload.flavor_id,
        image_id=payload.image_id,
        network_id=payload.network_id,
        key_name=payload.key_name,
        security_groups=payload.security_groups,
        user_data=payload.user_data,
        metadata=payload.metadata,
    )


@router.get("/{vm_id}", response_model=VMResponse, summary="Get VM details")
def get_vm(vm_id: str, svc: VMService = Depends(get_vm_service)):
    return svc.get_vm(vm_id)


@router.delete("/{vm_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Terminate a VM")
def delete_vm(vm_id: str, svc: VMService = Depends(get_vm_service)):
    svc.delete_vm(vm_id)


@router.post("/{vm_id}/action", response_model=VMResponse, summary="Perform a lifecycle action")
def vm_action(
    vm_id: str,
    payload: VMActionRequest,
    svc: VMService = Depends(get_vm_service),
):
    """
    Supported actions: start, stop, reboot, pause, unpause, suspend, resume, shelve, unshelve.

    For `reboot`, pass `"hard": true` to force a hard reboot.
    For `resize`, pass `"flavor_id"` with the target flavor.
    """
    return svc.perform_action(
        vm_id=vm_id,
        action=payload.action,
        hard=payload.hard or False,
        flavor_id=payload.flavor_id,
    )


@router.get("/{vm_id}/console", response_model=VMConsoleResponse, summary="Get console URL")
def get_console(
    vm_id: str,
    console_type: str = Query("novnc", description="Console type: novnc | spice-html5 | rdp-html5 | serial"),
    svc: VMService = Depends(get_vm_service),
):
    console = svc.get_console(vm_id, console_type=console_type)
    return VMConsoleResponse(type=console_type, url=console.url)
