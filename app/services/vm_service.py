"""
VM Service — wraps openstack SDK calls and translates them into
domain objects the API layer can work with cleanly.

Design note: all OpenStack SDK exceptions are caught here and re-raised
as our own domain exceptions so the router layer stays thin.
"""
import logging
from typing import Optional
import openstack
from openstack.exceptions import ResourceNotFound, HttpException

from app.config import Settings
from app.exceptions import VMNotFoundError, VMOperationError, OpenStackConnectionError
from app.schemas.vm import VMResponse, VMStatus

logger = logging.getLogger(__name__)

# Map OpenStack power states to something readable
POWER_STATE_MAP = {0: "NO STATE", 1: "RUNNING", 3: "PAUSED", 4: "SHUTDOWN", 6: "CRASHED", 7: "SUSPENDED"}

ALLOWED_ACTIONS = {"start", "stop", "reboot", "pause", "unpause", "suspend", "resume", "shelve", "unshelve"}


def _build_connection(settings: Settings) -> openstack.connection.Connection:
    try:
        conn = openstack.connect(
            auth_url=settings.os_auth_url,
            username=settings.os_username,
            password=settings.os_password,
            project_name=settings.os_project_name,
            user_domain_name=settings.os_user_domain_name,
            project_domain_name=settings.os_project_domain_name,
            region_name=settings.os_region_name,
        )
        return conn
    except Exception as exc:
        raise OpenStackConnectionError(str(exc)) from exc


def _serialize_server(server) -> VMResponse:
    """Convert an openstack Server resource to our VMResponse schema."""
    return VMResponse(
        id=server.id,
        name=server.name,
        status=VMStatus(server.status) if server.status in VMStatus._value2member_map_ else VMStatus.UNKNOWN,
        flavor=dict(server.flavor) if server.flavor else {},
        image=dict(server.image) if server.image else None,
        addresses=dict(server.addresses) if server.addresses else {},
        key_name=server.key_name,
        metadata=dict(server.metadata) if server.metadata else {},
        created_at=server.created_at,
        updated_at=server.updated_at,
        host_id=server.host_id,
        availability_zone=server.availability_zone,
        power_state=server.power_state,
        task_state=server.task_state,
    )


class VMService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._conn: Optional[openstack.connection.Connection] = None

    @property
    def conn(self) -> openstack.connection.Connection:
        # Lazy connect — avoids failing at import time in test environments
        if self._conn is None:
            self._conn = _build_connection(self._settings)
        return self._conn

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def list_vms(self, page: int = 1, page_size: int = 20, status_filter: Optional[str] = None):
        try:
            filters = {}
            if status_filter:
                filters["status"] = status_filter.upper()
            servers = list(self.conn.compute.servers(**filters))
            total = len(servers)
            start = (page - 1) * page_size
            paginated = servers[start: start + page_size]
            return [_serialize_server(s) for s in paginated], total
        except HttpException as exc:
            raise VMOperationError(f"Failed to list VMs: {exc}") from exc

    def get_vm(self, vm_id: str) -> VMResponse:
        try:
            server = self.conn.compute.get_server(vm_id)
            if server is None:
                raise VMNotFoundError(vm_id)
            return _serialize_server(server)
        except ResourceNotFound:
            raise VMNotFoundError(vm_id)
        except HttpException as exc:
            raise VMOperationError(str(exc), vm_id=vm_id) from exc

    def create_vm(self, name, flavor_id, image_id, network_id=None,
                  key_name=None, security_groups=None, user_data=None, metadata=None) -> VMResponse:
        try:
            networks = [{"uuid": network_id}] if network_id else []
            sgs = [{"name": sg} for sg in (security_groups or [])]
            server = self.conn.compute.create_server(
                name=name,
                flavor_id=flavor_id,
                image_id=image_id,
                networks=networks,
                key_name=key_name,
                security_groups=sgs or None,
                user_data=user_data,
                metadata=metadata or {},
            )
            # Wait briefly for the server record to be available
            server = self.conn.compute.wait_for_server(server, status="BUILD", failures=["ERROR"], interval=2, wait=10)
            return _serialize_server(server)
        except HttpException as exc:
            raise VMOperationError(f"Failed to create VM: {exc}") from exc

    def delete_vm(self, vm_id: str) -> None:
        try:
            server = self.conn.compute.get_server(vm_id)
            if server is None:
                raise VMNotFoundError(vm_id)
            self.conn.compute.delete_server(vm_id)
        except ResourceNotFound:
            raise VMNotFoundError(vm_id)
        except HttpException as exc:
            raise VMOperationError(str(exc), vm_id=vm_id) from exc

    # ------------------------------------------------------------------
    # Lifecycle actions
    # ------------------------------------------------------------------

    def perform_action(self, vm_id: str, action: str, hard: bool = False, flavor_id: str = None) -> VMResponse:
        if action not in ALLOWED_ACTIONS:
            raise VMOperationError(f"Unknown action '{action}'. Allowed: {sorted(ALLOWED_ACTIONS)}", vm_id=vm_id)

        try:
            server = self.conn.compute.get_server(vm_id)
            if server is None:
                raise VMNotFoundError(vm_id)

            dispatch = {
                "start":    lambda: self.conn.compute.start_server(vm_id),
                "stop":     lambda: self.conn.compute.stop_server(vm_id),
                "reboot":   lambda: self.conn.compute.reboot_server(vm_id, reboot_type="HARD" if hard else "SOFT"),
                "pause":    lambda: self.conn.compute.pause_server(vm_id),
                "unpause":  lambda: self.conn.compute.unpause_server(vm_id),
                "suspend":  lambda: self.conn.compute.suspend_server(vm_id),
                "resume":   lambda: self.conn.compute.resume_server(vm_id),
                "shelve":   lambda: self.conn.compute.shelve_server(vm_id),
                "unshelve": lambda: self.conn.compute.unshelve_server(vm_id),
            }
            dispatch[action]()
            # Re-fetch to return updated state
            return self.get_vm(vm_id)
        except (VMNotFoundError, VMOperationError):
            raise
        except HttpException as exc:
            raise VMOperationError(f"Action '{action}' failed: {exc}", vm_id=vm_id) from exc

    def get_console(self, vm_id: str, console_type: str = "novnc"):
        try:
            server = self.conn.compute.get_server(vm_id)
            if server is None:
                raise VMNotFoundError(vm_id)
            console = self.conn.compute.create_console(vm_id, console_type=console_type)
            return console
        except ResourceNotFound:
            raise VMNotFoundError(vm_id)
        except HttpException as exc:
            raise VMOperationError(str(exc), vm_id=vm_id) from exc
