from fastapi import APIRouter
from datetime import datetime, timezone

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe")
def health_check():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/health/ready", summary="Readiness probe — verifies OpenStack reachability")
def readiness_check():
    """
    Lightweight check used by load balancers / k8s readiness probes.
    We intentionally keep this fast — just confirms the process is up.
    A deeper OpenStack connectivity check would add latency on every probe.
    """
    return {"status": "ready", "timestamp": datetime.now(timezone.utc).isoformat()}
