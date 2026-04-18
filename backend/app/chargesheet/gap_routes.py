"""Chargesheet Gap Analysis API endpoints — T56-E3.

Mounted at /api/v1/chargesheet/{chargesheet_id}/gaps
"""

from __future__ import annotations

import io
import json
import logging
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.core.rbac import Role, get_current_user, require_role
from app.db.session import get_connection
from app.chargesheet.gap_aggregator import (
    add_gap_action,
    aggregate_gaps,
    get_gap_action_history,
    get_latest_report,
    get_report_by_id,
    list_reports,
)
from app.chargesheet.gap_schemas import (
    ApplySuggestionRequest,
    GapActionRequest,
    GapActionResponse,
    GapReportResponse,
    GapReportSummary,
    GapResponse,
    ReanalyzeRequest,
    ReadinessCategory,
    ReadinessResponse,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["chargesheet-gaps"])

_WRITE_ROLES = (Role.IO, Role.SHO, Role.DYSP, Role.SP, Role.ADMIN)
_READ_ROLES = (Role.IO, Role.SHO, Role.DYSP, Role.SP, Role.ADMIN, Role.READONLY)
_EXPORT_ROLES = (Role.IO, Role.SHO, Role.DYSP, Role.SP, Role.ADMIN)
_DISTRICT_SCOPED = {Role.IO.value, Role.SHO.value}


def _check_scope(user: dict, cs: dict) -> None:
    if user["role"] in _DISTRICT_SCOPED and cs.get("district"):
        if cs["district"] != user.get("district"):
            raise HTTPException(status_code=403, detail="Not in your district scope")


def _get_cs_or_404(conn, cs_id: UUID) -> dict:
    import psycopg2.extras
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM chargesheets WHERE id = %s", (cs_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Chargesheet '{cs_id}' not found")
        return dict(row)


def _report_to_response(report: dict) -> GapReportResponse:
    gaps = []
    for g in report.get("gaps", []):
        legal_refs = g.get("legal_refs") or []
        if isinstance(legal_refs, str):
            legal_refs = json.loads(legal_refs)
        remediation = g.get("remediation") or {}
        if isinstance(remediation, str):
            remediation = json.loads(remediation)
        location = g.get("location")
        if isinstance(location, str):
            location = json.loads(location)

        gaps.append(GapResponse(
            id=g["id"], report_id=g["report_id"],
            category=g["category"], severity=g["severity"],
            source=g["source"], requires_disclaimer=g["requires_disclaimer"],
            title=g["title"], description_md=g.get("description_md"),
            location=location, legal_refs=legal_refs,
            remediation=remediation,
            related_mindmap_node_id=g.get("related_mindmap_node_id"),
            confidence=float(g.get("confidence", 0)),
            tags=g.get("tags") or [],
            display_order=g.get("display_order", 0),
            current_action=g.get("current_action"),
        ))

    return GapReportResponse(
        id=report["id"], chargesheet_id=report["chargesheet_id"],
        generated_at=report["generated_at"],
        generator_version=report["generator_version"],
        gap_count=report["gap_count"],
        critical_count=report["critical_count"],
        high_count=report["high_count"],
        medium_count=report["medium_count"],
        low_count=report["low_count"],
        advisory_count=report["advisory_count"],
        generation_duration_ms=report.get("generation_duration_ms"),
        gaps=gaps,
    )


# ── POST /analyze — Generate gap report (idempotent) ────────────────────────

@router.post(
    "/chargesheet/{chargesheet_id}/gaps/analyze",
    response_model=GapReportResponse,
    status_code=201,
    summary="Analyze chargesheet gaps",
)
def analyze_endpoint(
    chargesheet_id: UUID,
    user: dict = Depends(require_role(*_WRITE_ROLES)),
):
    try:
        conn = get_connection()
        cs = _get_cs_or_404(conn, chargesheet_id)
        _check_scope(user, cs)
        report = aggregate_gaps(chargesheet_id, conn=conn)
        logger.info("chargesheet.gap_report_generated",
                     chargesheet_id=str(chargesheet_id), user=user["username"])
        return _report_to_response(report)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("gap.analyze_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /report — Latest report ─────────────────────────────────────────────

@router.get(
    "/chargesheet/{chargesheet_id}/gaps/report",
    response_model=GapReportResponse,
    summary="Get latest gap report",
)
def get_report_endpoint(
    chargesheet_id: UUID,
    user: dict = Depends(require_role(*_READ_ROLES)),
):
    try:
        conn = get_connection()
        cs = _get_cs_or_404(conn, chargesheet_id)
        _check_scope(user, cs)
        report = get_latest_report(conn, chargesheet_id)
        if not report:
            raise HTTPException(status_code=404, detail="No gap report yet")
        return _report_to_response(report)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("gap.get_report_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /reports — All historical versions ───────────────────────────────────

@router.get(
    "/chargesheet/{chargesheet_id}/gaps/reports",
    response_model=list[GapReportSummary],
    summary="List gap report versions",
)
def list_reports_endpoint(
    chargesheet_id: UUID,
    user: dict = Depends(require_role(*_READ_ROLES)),
):
    try:
        conn = get_connection()
        cs = _get_cs_or_404(conn, chargesheet_id)
        _check_scope(user, cs)
        return [GapReportSummary(**r) for r in list_reports(conn, chargesheet_id)]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /reports/{report_id} — Specific version ─────────────────────────────

@router.get(
    "/chargesheet/{chargesheet_id}/gaps/reports/{report_id}",
    response_model=GapReportResponse,
    summary="Get specific gap report version",
)
def get_specific_report_endpoint(
    chargesheet_id: UUID,
    report_id: UUID,
    user: dict = Depends(require_role(*_READ_ROLES)),
):
    try:
        conn = get_connection()
        cs = _get_cs_or_404(conn, chargesheet_id)
        _check_scope(user, cs)
        report = get_report_by_id(conn, report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        return _report_to_response(report)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── POST /reanalyze — Force new report ───────────────────────────────────────

@router.post(
    "/chargesheet/{chargesheet_id}/gaps/reanalyze",
    response_model=GapReportResponse,
    status_code=201,
    summary="Force reanalysis",
)
def reanalyze_endpoint(
    chargesheet_id: UUID,
    payload: ReanalyzeRequest,
    user: dict = Depends(require_role(*_WRITE_ROLES)),
):
    try:
        conn = get_connection()
        cs = _get_cs_or_404(conn, chargesheet_id)
        _check_scope(user, cs)
        report = aggregate_gaps(chargesheet_id, conn=conn, regenerate=True)
        logger.info("chargesheet.gap_report_regenerated",
                     chargesheet_id=str(chargesheet_id),
                     justification=payload.justification, user=user["username"])
        return _report_to_response(report)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── PATCH /{gap_id}/action — Act on a gap ────────────────────────────────────

@router.patch(
    "/chargesheet/{chargesheet_id}/gaps/{gap_id}/action",
    response_model=GapActionResponse,
    summary="Act on a gap (append-only)",
)
def gap_action_endpoint(
    chargesheet_id: UUID,
    gap_id: UUID,
    payload: GapActionRequest,
    user: dict = Depends(require_role(*_WRITE_ROLES)),
):
    try:
        conn = get_connection()
        cs = _get_cs_or_404(conn, chargesheet_id)
        _check_scope(user, cs)
        result = add_gap_action(
            conn, gap_id, user_id=user["username"],
            action=payload.action.value, note=payload.note or "",
            modification_diff=payload.modification_diff or "",
            evidence_ref=payload.evidence_ref or "",
            hash_prev=payload.hash_prev,
        )
        logger.info("chargesheet.gap_action_taken", gap_id=str(gap_id),
                     action=payload.action.value, user=user["username"])
        return GapActionResponse(**result)
    except ValueError as e:
        if "Hash chain conflict" in str(e):
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /{gap_id}/history — Action chain ─────────────────────────────────────

@router.get(
    "/chargesheet/{chargesheet_id}/gaps/{gap_id}/history",
    response_model=list[GapActionResponse],
    summary="Gap action history",
)
def gap_history_endpoint(
    chargesheet_id: UUID,
    gap_id: UUID,
    user: dict = Depends(require_role(*_READ_ROLES)),
):
    try:
        conn = get_connection()
        cs = _get_cs_or_404(conn, chargesheet_id)
        _check_scope(user, cs)
        return [GapActionResponse(**h) for h in get_gap_action_history(conn, gap_id)]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── POST /{gap_id}/apply-suggestion — Apply suggested language ───────────────

@router.post(
    "/chargesheet/{chargesheet_id}/gaps/{gap_id}/apply-suggestion",
    response_model=GapActionResponse,
    status_code=201,
    summary="Apply AI suggestion to chargesheet",
)
def apply_suggestion_endpoint(
    chargesheet_id: UUID,
    gap_id: UUID,
    payload: ApplySuggestionRequest,
    user: dict = Depends(require_role(*_WRITE_ROLES)),
):
    try:
        conn = get_connection()
        cs = _get_cs_or_404(conn, chargesheet_id)
        _check_scope(user, cs)

        # Fetch the gap to get suggested_language
        import psycopg2.extras
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM chargesheet_gaps WHERE id = %s", (gap_id,))
            gap = cur.fetchone()
            if not gap:
                raise HTTPException(status_code=404, detail="Gap not found")

        remediation = gap.get("remediation") or {}
        if isinstance(remediation, str):
            remediation = json.loads(remediation)
        suggested = remediation.get("suggested_language")
        if not suggested:
            raise HTTPException(status_code=422,
                                detail="No suggested language available for this gap")

        # Get latest hash for this gap's action chain
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT hash_self FROM chargesheet_gap_actions
                   WHERE gap_id = %s ORDER BY created_at DESC LIMIT 1""",
                (gap_id,),
            )
            latest = cur.fetchone()
            hash_prev = latest["hash_self"] if latest else "GENESIS"

        result = add_gap_action(
            conn, gap_id, user_id=user["username"],
            action="modified",
            note=f"Applied AI suggestion: {suggested[:100]}...",
            modification_diff=suggested,
            hash_prev=hash_prev,
        )
        logger.info("chargesheet.suggestion_applied", gap_id=str(gap_id),
                     chargesheet_id=str(chargesheet_id), user=user["username"])
        return GapActionResponse(**result)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /export/clean-pdf ────────────────────────────────────────────────────

@router.get(
    "/chargesheet/{chargesheet_id}/gaps/export/clean-pdf",
    summary="Export clean court-ready PDF",
)
def export_clean_pdf(
    chargesheet_id: UUID,
    user: dict = Depends(require_role(*_EXPORT_ROLES)),
):
    try:
        conn = get_connection()
        cs = _get_cs_or_404(conn, chargesheet_id)
        _check_scope(user, cs)

        html = _render_clean_html(cs)
        logger.info("chargesheet.exported", export_type="clean-pdf",
                     chargesheet_id=str(chargesheet_id), user=user["username"])

        try:
            from weasyprint import HTML
            pdf = HTML(string=html).write_pdf()
            return StreamingResponse(
                io.BytesIO(pdf), media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="chargesheet_{chargesheet_id}.pdf"'},
            )
        except ImportError:
            return StreamingResponse(
                io.BytesIO(html.encode()), media_type="text/html",
                headers={"Content-Disposition": f'attachment; filename="chargesheet_{chargesheet_id}.html"'},
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /export/review-report ────────────────────────────────────────────────

@router.get(
    "/chargesheet/{chargesheet_id}/gaps/export/review-report",
    summary="Export AI review report PDF",
)
def export_review_report(
    chargesheet_id: UUID,
    user: dict = Depends(require_role(*_EXPORT_ROLES)),
):
    try:
        conn = get_connection()
        cs = _get_cs_or_404(conn, chargesheet_id)
        _check_scope(user, cs)
        report = get_latest_report(conn, chargesheet_id)
        if not report:
            raise HTTPException(status_code=404, detail="No gap report")

        html = _render_review_html(cs, report)
        logger.info("chargesheet.exported", export_type="review-report",
                     chargesheet_id=str(chargesheet_id), user=user["username"])

        try:
            from weasyprint import HTML
            pdf = HTML(string=html).write_pdf()
            return StreamingResponse(
                io.BytesIO(pdf), media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="review_{chargesheet_id}.pdf"'},
            )
        except ImportError:
            return StreamingResponse(
                io.BytesIO(html.encode()), media_type="text/html",
                headers={"Content-Disposition": f'attachment; filename="review_{chargesheet_id}.html"'},
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /export/redline ──────────────────────────────────────────────────────

@router.get(
    "/chargesheet/{chargesheet_id}/gaps/export/redline",
    summary="Export redline diff PDF",
)
def export_redline(
    chargesheet_id: UUID,
    user: dict = Depends(require_role(*_EXPORT_ROLES)),
):
    try:
        conn = get_connection()
        cs = _get_cs_or_404(conn, chargesheet_id)
        _check_scope(user, cs)

        html = _render_redline_html(cs)
        logger.info("chargesheet.exported", export_type="redline",
                     chargesheet_id=str(chargesheet_id), user=user["username"])

        try:
            from weasyprint import HTML
            pdf = HTML(string=html).write_pdf()
            return StreamingResponse(
                io.BytesIO(pdf), media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="redline_{chargesheet_id}.pdf"'},
            )
        except ImportError:
            return StreamingResponse(
                io.BytesIO(html.encode()), media_type="text/html",
                headers={"Content-Disposition": f'attachment; filename="redline_{chargesheet_id}.html"'},
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── HTML renderers ───────────────────────────────────────────────────────────

def _render_clean_html(cs: dict) -> str:
    """Court-ready clean chargesheet — ZERO AI annotations."""
    charges = cs.get("charges_json") or []
    if isinstance(charges, str):
        charges = json.loads(charges)
    accused = cs.get("accused_json") or []
    if isinstance(accused, str):
        accused = json.loads(accused)

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>body{{font-family:Arial,sans-serif;margin:2cm;font-size:11pt}}
h1{{text-align:center;font-size:14pt}} h2{{font-size:12pt;margin-top:16px}}
table{{border-collapse:collapse;width:100%}} td,th{{border:1px solid #000;padding:6px;font-size:10pt}}
.header{{text-align:center;margin-bottom:20px}} .footer{{margin-top:30px;font-size:9pt}}
</style></head><body>
<div class="header"><h1>CHARGESHEET</h1>
<p>Under Section 173 CrPC / 193 BNSS</p></div>
<h2>Case Details</h2>
<table><tr><td><b>Court</b></td><td>{cs.get('court_name', '—')}</td></tr>
<tr><td><b>FIR Reference</b></td><td>{cs.get('fir_reference_number', cs.get('fir_id', '—'))}</td></tr>
<tr><td><b>Filing Date</b></td><td>{cs.get('filing_date', '—')}</td></tr>
<tr><td><b>IO</b></td><td>{cs.get('io_name', '—')}</td></tr>
<tr><td><b>District</b></td><td>{cs.get('district', '—')}</td></tr>
<tr><td><b>Police Station</b></td><td>{cs.get('police_station', '—')}</td></tr></table>
<h2>Charges</h2><table><tr><th>Section</th><th>Act</th><th>Description</th></tr>
{''.join(f"<tr><td>{c.get('section','—')}</td><td>{c.get('act','—')}</td><td>{c.get('description','—')}</td></tr>" for c in charges)}
</table>
<h2>Accused Persons</h2><table><tr><th>Name</th><th>Age</th><th>Address</th><th>Role</th></tr>
{''.join(f"<tr><td>{a.get('name','—')}</td><td>{a.get('age','—')}</td><td>{a.get('address','—')}</td><td>{a.get('role','—')}</td></tr>" for a in accused)}
</table>
<div class="footer"><p>Filed by: {cs.get('io_name', '—')}</p></div>
</body></html>"""


def _render_review_html(cs: dict, report: dict) -> str:
    """Internal AI review report with watermark and disclaimer."""
    gaps = report.get("gaps", [])
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>body{{font-family:Arial,sans-serif;margin:2cm;font-size:10pt}}
.watermark{{position:fixed;top:40%;left:10%;transform:rotate(-45deg);font-size:60pt;
color:rgba(200,200,200,0.3);z-index:-1;white-space:nowrap}}
.disclaimer{{background:#fff3cd;border:1px solid #ffc107;padding:10px;margin-bottom:20px;font-size:9pt}}
h1{{font-size:14pt}} h2{{font-size:12pt;margin-top:18px}}
.gap{{margin:8px 0;padding:8px;border:1px solid #ddd;border-radius:4px}}
.critical{{border-left:4px solid #dc3545}} .high{{border-left:4px solid #fd7e14}}
.medium{{border-left:4px solid #ffc107}} .low{{border-left:4px solid #0d6efd}}
.sev{{font-weight:bold;text-transform:uppercase;font-size:9pt;padding:2px 6px;border-radius:3px}}
</style></head><body>
<div class="watermark">INTERNAL REVIEW — NOT FOR COURT SUBMISSION</div>
<h1>AI Review Report — Chargesheet</h1>
<div class="disclaimer"><b>Advisory:</b> AI-assisted review. Investigating Officer retains
full legal responsibility. Not a substitute for legal judgment or supervisor review.</div>
<p><b>Chargesheet ID:</b> {report['chargesheet_id']}</p>
<p><b>Generated:</b> {report['generated_at']}</p>
<p><b>Version:</b> {report['generator_version']}</p>
<p><b>Gaps:</b> {report['gap_count']} total | {report['critical_count']} critical |
{report['high_count']} high | {report['medium_count']} medium |
{report['low_count']} low | {report['advisory_count']} advisory</p>
<h2>Gap Analysis</h2>
{''.join(_render_gap_html(g) for g in gaps)}
<div class="disclaimer" style="margin-top:30px"><b>Disclaimer:</b> This report was generated
by ATLAS AI review system v{report['generator_version']}. All findings are advisory.
The Investigating Officer bears full responsibility for chargesheet completeness.</div>
</body></html>"""


def _render_gap_html(g: dict) -> str:
    sev = g.get("severity", "medium")
    remediation = g.get("remediation") or {}
    if isinstance(remediation, str):
        remediation = json.loads(remediation)
    action = g.get("current_action", "open")
    return f"""<div class="gap {sev}">
<span class="sev">{sev}</span> [{g.get('category','')}] <b>{g.get('title','')}</b>
<span style="float:right;font-size:9pt">Status: {action or 'open'}</span>
<p style="font-size:9pt;color:#555">{g.get('description_md','')}</p>
<p style="font-size:9pt"><b>Remediation:</b> {remediation.get('summary','')}</p>
</div>"""


def _render_redline_html(cs: dict) -> str:
    """Redline view placeholder — shows current chargesheet text."""
    raw = cs.get("raw_text") or "No text content available"
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>body{{font-family:Arial,sans-serif;margin:2cm;font-size:10pt}}
.watermark{{position:fixed;top:40%;left:15%;transform:rotate(-45deg);font-size:50pt;
color:rgba(200,200,200,0.3);z-index:-1;white-space:nowrap}}
h1{{font-size:14pt}} .text{{white-space:pre-wrap;font-size:10pt;line-height:1.6}}
ins{{background:#d4edda;text-decoration:underline}} del{{background:#f8d7da;text-decoration:line-through}}
</style></head><body>
<div class="watermark">REDLINE — SUPERVISOR REVIEW</div>
<h1>Redline View — Chargesheet {cs.get('id','')}</h1>
<div class="text">{raw}</div>
</body></html>"""
