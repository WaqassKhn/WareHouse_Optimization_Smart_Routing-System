from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any

from app.services.analytics import build_dashboard_snapshot, summarize_operational_health


def build_operational_report(format: str = "json") -> dict[str, Any] | str:
    snapshot = build_dashboard_snapshot()
    health = summarize_operational_health(snapshot)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "title": "Warehouse Optimization Operational Report",
        "health": health,
        "kpis": snapshot["kpis"],
        "picking_summary": snapshot["picking"]["summary"],
        "delivery_summary": snapshot["delivery"]["summary"],
        "recommendations": snapshot["recommendations"],
    }
    if format == "csv":
        return _report_to_csv(report)
    return report


def _report_to_csv(report: dict[str, Any]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["section", "metric", "value"])
    writer.writerow(["report", "generated_at", report["generated_at"]])
    writer.writerow(["health", "overall_score", report["health"]["overall_score"]])
    writer.writerow(["health", "risk_level", report["health"]["risk_level"]])
    writer.writerow(["health", "primary_constraint", report["health"]["primary_constraint"]])

    for key, value in report["kpis"].items():
        writer.writerow(["kpi", key, value])
    for key, value in report["picking_summary"].items():
        writer.writerow(["picking", key, value])
    for key, value in report["delivery_summary"].items():
        writer.writerow(["delivery", key, value])
    for recommendation in report["recommendations"]:
        writer.writerow(
            [
                "recommendation",
                recommendation["type"],
                f"{recommendation['priority']}: {recommendation['title']} - {recommendation['action']}",
            ]
        )
    return output.getvalue()

