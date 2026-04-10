"""
Test fixtures.

We mock the VMService entirely so tests never need a live OpenStack.
This keeps the test suite fast and runnable in CI without any infra.
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime, timezone

from app.main import app
from app.dependencies import get_vm_service
from app.schemas.vm import VMResponse, VMStatus


def _make_vm(vm_id="vm-001", name="test-vm", status=VMStatus.ACTIVE) -> VMResponse:
    return VMResponse(
        id=vm_id,
        name=name,
        status=status,
        flavor={"id": "m1.small", "vcpus": 1, "ram": 2048},
        image={"id": "img-001", "name": "ubuntu-22.04"},
        addresses={"default": [{"addr": "192.168.1.10", "version": 4}]},
        key_name="my-key",
        metadata={},
        created_at=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 15, 10, 5, 0, tzinfo=timezone.utc),
        host_id="opaque-host-id",
        availability_zone="nova",
        power_state=1,
        task_state=None,
    )


@pytest.fixture
def mock_svc():
    svc = MagicMock()
    svc.list_vms.return_value = ([_make_vm()], 1)
    svc.get_vm.return_value = _make_vm()
    svc.create_vm.return_value = _make_vm(status=VMStatus.BUILD)
    svc.perform_action.return_value = _make_vm(status=VMStatus.STOPPED)
    return svc


@pytest.fixture
def client(mock_svc):
    app.dependency_overrides[get_vm_service] = lambda: mock_svc
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
