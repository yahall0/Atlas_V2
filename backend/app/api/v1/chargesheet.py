from fastapi import APIRouter

router = APIRouter(prefix="/chargesheet", tags=["chargesheet"])


@router.get("/health")
def chargesheet_health():
    return {"status": "ok", "module": "chargesheet"}
