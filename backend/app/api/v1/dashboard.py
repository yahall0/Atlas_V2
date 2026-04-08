from fastapi import APIRouter

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/health")
def dashboard_health():
    return {"status": "ok", "module": "dashboard"}


@router.get("/stats")
def dashboard_stats():
    return {"total_firs": 0, "districts": 6, "pending_review": 0}
