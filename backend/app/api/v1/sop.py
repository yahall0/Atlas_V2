from fastapi import APIRouter

router = APIRouter(prefix="/sop", tags=["sop"])


@router.get("/health")
def sop_health():
    return {"status": "ok", "module": "sop"}
