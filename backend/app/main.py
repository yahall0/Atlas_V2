import logging

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.health import router as health_router
from app.api.v1.firs import router as firs_router
from app.api.v1.auth import router as auth_router
from app.api.v1.chargesheet import router as chargesheet_router
from app.api.v1.sop import router as sop_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.predict import router as predict_router
from app.api.v1.validate import router as validate_router
from app.api.v1.evidence import router as evidence_router
from app.api.v1.review import router as review_router
from app.mindmap.routes import router as mindmap_router
from app.chargesheet.gap_routes import router as gap_routes_router
from app.mindmap.kb.routes import router as kb_router

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)
logging.basicConfig(level=logging.INFO)

logger = structlog.get_logger(__name__)

app = FastAPI(title="ATLAS API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1")
app.include_router(firs_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1/auth")
app.include_router(chargesheet_router, prefix="/api/v1")
app.include_router(sop_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(predict_router, prefix="/api/v1")
app.include_router(validate_router, prefix="/api/v1")
app.include_router(evidence_router, prefix="/api/v1")
app.include_router(review_router, prefix="/api/v1")
app.include_router(mindmap_router, prefix="/api/v1")
app.include_router(gap_routes_router, prefix="/api/v1")
app.include_router(kb_router, prefix="/api/v1")

try:
    from app.api.v1.ingest import router as ingest_router
    app.include_router(ingest_router, prefix="/api/v1")
except ImportError:
    pass

try:
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app).expose(app)
except ImportError:
    pass


@app.on_event("startup")
def startup_event():
    logger.info("ATLAS backend starting")

    # Validate mindmap templates at startup (T53-M2)
    import os
    if os.getenv("ATLAS_MINDMAP_ENABLED", "true").lower() in ("1", "true", "yes"):
        try:
            from app.mindmap.registry import reload_templates
            reload_templates()
            logger.info("Mindmap template registry loaded successfully")
        except Exception as exc:
            logger.error("Mindmap template validation failed", error=str(exc))
            raise


@app.get("/")
def root():
    return {"message": "ATLAS backend running"}
