"""
Unit tests for VM lifecycle endpoints.
All OpenStack calls are mocked — no live infra required.
"""
import pytest
from app.exceptions import VMNotFoundError, VMOperationError


class TestHealth:
    def test_liveness(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_readiness(self, client):
        r = client.get("/health/ready")
        assert r.status_code == 200


class TestListVMs:
    def test_returns_paginated_list(self, client):
        r = client.get("/api/v1/vms")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["name"] == "test-vm"

    def test_pagination_params_forwarded(self, client, mock_svc):
        client.get("/api/v1/vms?page=2&page_size=5")
        mock_svc.list_vms.assert_called_once_with(page=2, page_size=5, status_filter=None)

    def test_status_filter_forwarded(self, client, mock_svc):
        client.get("/api/v1/vms?status=ACTIVE")
        mock_svc.list_vms.assert_called_once_with(page=1, page_size=20, status_filter="ACTIVE")


class TestGetVM:
    def test_returns_vm(self, client):
        r = client.get("/api/v1/vms/vm-001")
        assert r.status_code == 200
        assert r.json()["id"] == "vm-001"

    def test_not_found_returns_404(self, client, mock_svc):
        mock_svc.get_vm.side_effect = VMNotFoundError("bad-id")
        r = client.get("/api/v1/vms/bad-id")
        assert r.status_code == 404
        assert "bad-id" in r.json()["detail"]


class TestCreateVM:
    def test_create_returns_202(self, client):
        payload = {
            "name": "new-vm",
            "flavor_id": "m1.small",
            "image_id": "ubuntu-22.04",
        }
        r = client.post("/api/v1/vms", json=payload)
        assert r.status_code == 202
        assert r.json()["status"] == "BUILD"

    def test_missing_required_fields_returns_422(self, client):
        r = client.post("/api/v1/vms", json={"name": "oops"})
        assert r.status_code == 422


class TestDeleteVM:
    def test_delete_returns_204(self, client):
        r = client.delete("/api/v1/vms/vm-001")
        assert r.status_code == 204

    def test_delete_not_found_returns_404(self, client, mock_svc):
        mock_svc.delete_vm.side_effect = VMNotFoundError("ghost-vm")
        r = client.delete("/api/v1/vms/ghost-vm")
        assert r.status_code == 404


class TestVMAction:
    def test_stop_action(self, client):
        r = client.post("/api/v1/vms/vm-001/action", json={"action": "stop"})
        assert r.status_code == 200
        assert r.json()["status"] == "STOPPED"

    def test_invalid_action_returns_409(self, client, mock_svc):
        mock_svc.perform_action.side_effect = VMOperationError("Unknown action 'explode'")
        r = client.post("/api/v1/vms/vm-001/action", json={"action": "explode"})
        assert r.status_code == 409

    def test_hard_reboot(self, client, mock_svc):
        from app.schemas.vm import VMStatus
        mock_svc.perform_action.return_value = mock_svc.perform_action.return_value
        client.post("/api/v1/vms/vm-001/action", json={"action": "reboot", "hard": True})
        mock_svc.perform_action.assert_called_once_with(
            vm_id="vm-001", action="reboot", hard=True, flavor_id=None
        )
