from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.routers.auth import require_roles
from app.schemas import ReportFormat, Role
from app.services.reports import build_operational_report


router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/operational")
def operational_report(
    format: ReportFormat = ReportFormat.json,
    _user=Depends(require_roles(Role.admin, Role.planner, Role.analyst)),
):
    report = build_operational_report(format.value)
    if format == ReportFormat.csv:
        return Response(
            content=report,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=warehouse-operational-report.csv"},
        )
    return report

