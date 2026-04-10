# OpenStack VM Lifecycle API

A REST API for managing OpenStack virtual machine lifecycle operations — provisioning, power management, and console access. Built as a proof-of-concept demonstrating API design, Python best practices, and DevOps fundamentals.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [API Design](#api-design)
- [Getting Started](#getting-started)
- [Running Tests](#running-tests)
- [Docker](#docker)
- [Design Decisions](#design-decisions)
- [Roadmap](#roadmap)

---

## Overview

This service wraps the OpenStack Compute (Nova) API behind a clean, versioned REST interface. The goal is to give operators and automation tooling a consistent, well-documented surface for VM lifecycle management without coupling directly to OpenStack SDK internals.

**Supported operations:**

| Operation | Endpoint |
|---|---|
| List VMs (paginated, filterable) | `GET /api/v1/vms` |
| Provision a VM | `POST /api/v1/vms` |
| Get VM details | `GET /api/v1/vms/{id}` |
| Terminate a VM | `DELETE /api/v1/vms/{id}` |
| Lifecycle action (start/stop/reboot/etc.) | `POST /api/v1/vms/{id}/action` |
| Get console URL | `GET /api/v1/vms/{id}/console` |
| Health / readiness probes | `GET /health`, `GET /health/ready` |

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   FastAPI Application                │
│                                                      │
│  ┌──────────┐   ┌──────────────┐   ┌─────────────┐  │
│  │  Router  │──▶│  VMService   │──▶│ openstacksdk│  │
│  │ (HTTP)   │   │ (business    │   │ (Nova/      │  │
│  │          │   │  logic)      │   │  Keystone)  │  │
│  └──────────┘   └──────────────┘   └─────────────┘  │
│       │                                              │
│  ┌──────────┐   ┌──────────────┐                     │
│  │ Pydantic │   │  Exception   │                     │
│  │ Schemas  │   │  Handlers    │                     │
│  └──────────┘   └──────────────┘                     │
└─────────────────────────────────────────────────────┘
```

**Layer responsibilities:**

- `routers/` — HTTP concerns only: request parsing, response shaping, status codes
- `services/` — all OpenStack SDK calls, error translation, business rules
- `schemas/` — Pydantic models for validation and serialization
- `exceptions.py` — domain exceptions mapped to HTTP responses centrally
- `config.py` — environment-driven settings via pydantic-settings

---

## API Design

### Versioning

All endpoints are prefixed with `/api/v1`. Version is in the URL path rather than a header — easier to test, bookmark, and proxy.

### Async provisioning (202 pattern)

`POST /api/v1/vms` returns `202 Accepted` rather than `201 Created`. OpenStack builds VMs asynchronously — the VM is in `BUILD` status immediately after the API call. Callers should poll `GET /api/v1/vms/{id}` until status transitions to `ACTIVE` or `ERROR`.

### Lifecycle actions via sub-resource

Rather than separate endpoints per action (`/vms/{id}/stop`, `/vms/{id}/start`), all lifecycle operations go through `POST /vms/{id}/action` with an `action` field. This keeps the URL surface small and mirrors how OpenStack's own API works, which makes the mapping transparent.

```json
POST /api/v1/vms/{id}/action
{
  "action": "reboot",
  "hard": true
}
```

Supported actions: `start`, `stop`, `reboot`, `pause`, `unpause`, `suspend`, `resume`, `shelve`, `unshelve`

### Error responses

All errors return a consistent shape:

```json
{
  "detail": "VM 'abc-123' not found",
  "vm_id": "abc-123"
}
```

HTTP status mapping:
- `404` — VM not found
- `409` — Operation conflict (wrong state, invalid action)
- `422` — Request validation failure (Pydantic)
- `503` — OpenStack unreachable

---

## Getting Started

### Prerequisites

- Python 3.12+
- Access to an OpenStack environment (or DevStack for local testing)

### Install

```bash
git clone <repo-url>
cd openstack-vm-lifecycle-api

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
# Edit .env with your OpenStack credentials
```

### Run

```bash
uvicorn app.main:app --reload
```

API docs available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## API Usage Examples

### Provision a VM
```bash
curl -X POST http://localhost:8000/api/v1/vms \
  -H "Content-Type: application/json" \
  -d '{
    "name": "web-server-01",
    "flavor_id": "m1.small",
    "image_id": "ubuntu-22.04",
    "key_name": "my-keypair",
    "security_groups": ["default"]
  }'
```

### List VMs (with status filter)
```bash
curl "http://localhost:8000/api/v1/vms?status=ACTIVE&page=1&page_size=10"
```

### Get a specific VM
```bash
curl http://localhost:8000/api/v1/vms/<vm-id>
```

### Stop a VM
```bash
curl -X POST http://localhost:8000/api/v1/vms/<vm-id>/action \
  -H "Content-Type: application/json" \
  -d '{"action": "stop"}'
```

### Hard reboot
```bash
curl -X POST http://localhost:8000/api/v1/vms/<vm-id>/action \
  -H "Content-Type: application/json" \
  -d '{"action": "reboot", "hard": true}'
```

### Get VNC console URL
```bash
curl "http://localhost:8000/api/v1/vms/<vm-id>/console?console_type=novnc"
```

### Delete a VM
```bash
curl -X DELETE http://localhost:8000/api/v1/vms/<vm-id>
# Returns 204 No Content on success
```

---

## Running Tests

Tests mock the VMService entirely — no live OpenStack required.

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

---

## Docker

```bash
# Build and run
docker-compose up --build

# Or standalone
docker build -t vm-lifecycle-api .
docker run -p 8000:8000 --env-file .env vm-lifecycle-api
```

---

## Design Decisions

**Why FastAPI over Flask/Django?**
FastAPI gives us automatic OpenAPI docs, Pydantic validation, and async support out of the box. For an API-first service this is the right tradeoff — less boilerplate, better developer experience.

**Why openstacksdk over direct Nova HTTP calls?**
openstacksdk handles Keystone token management, endpoint discovery, and retry logic. Rolling our own HTTP client would duplicate that work and introduce subtle auth bugs.

**Why a service layer instead of calling SDK directly from routers?**
Keeps routers thin and testable. The service layer is the only place that knows about OpenStack — swapping the backend (e.g. mocking for tests, or adding a caching layer) doesn't touch the HTTP layer.

**Why module-level singleton for VMService?**
Re-authenticating against Keystone on every request adds ~100-300ms latency. The singleton reuses the token until it expires, then re-authenticates transparently via openstacksdk's session management.

**Why 202 for VM creation?**
OpenStack VM provisioning is inherently async. Returning 201 would imply the resource is ready, which it isn't. 202 sets the right expectation and avoids clients assuming they can immediately SSH in.

---

## Roadmap

Items scoped out of this timebox but worth building next:

**Short term**
- `GET /api/v1/vms/{id}/metrics` — CPU/memory/disk utilization via Ceilometer or Gnocchi
- Resize endpoint with flavor validation before submission
- Async task tracking — return a `task_id` on long operations, poll `/tasks/{id}`
- Rate limiting middleware (slowapi)

**Medium term**
- Auth middleware — JWT or Keystone token passthrough so callers use their own credentials
- Bulk operations — `POST /api/v1/vms/bulk-action` for fleet management
- Webhook support — push status change events to a caller-provided URL
- OpenTelemetry tracing for distributed observability

**Longer term**
- Multi-region support — route requests to the correct OpenStack region based on VM location
- Terraform provider wrapping this API
- Async worker (Celery/ARQ) for long-running operations to avoid HTTP timeouts
- Admin dashboard (read-only) for fleet visibility
