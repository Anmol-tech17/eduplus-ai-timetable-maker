"""
backend/app/ai/explainer.py
EduPlus AI Timetable Maker — Grounded Timetable & Validation AI Explainer

Translates raw solver outputs, validation violation codes, and version diffs
into clear, actionable, institutional markdown summaries and insights.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.app.ai.provider import get_llm_provider
from backend.app.ai.schemas import ExplanationResponse
from backend.app.engine.comparator import compare_versions
from backend.app.models.timetable import GenerationRun, TimetableVersion, Violation

logger = logging.getLogger("eduplus.ai.explainer")


def explain_generation(
    version_id: Optional[str],
    run_id: Optional[str],
    db: Session,
    custom_payload: Optional[Dict[str, Any]] = None,
) -> ExplanationResponse:
    """
    Generate plain-language explanation for a timetable version or generation run.
    """
    provider = get_llm_provider()

    if custom_payload:
        data = custom_payload
    else:
        version = None
        run = None
        if version_id:
            version = db.query(TimetableVersion).filter(TimetableVersion.id == version_id).first()
        if run_id:
            run = db.query(GenerationRun).filter(GenerationRun.id == run_id).first()
        elif version and version.generation_runs:
            run = version.generation_runs[-1]

        violations = []
        if version:
            violations_db = db.query(Violation).filter(Violation.version_id == version.id).all()
            violations = [
                {
                    "rule_id": v.rule_id,
                    "level": v.level,
                    "severity": v.severity,
                    "description": v.description,
                    "affected_sessions": v.affected_sessions,
                }
                for v in violations_db
            ]

        hard_count = sum(1 for v in violations if v.get("level") == "A")
        soft_count = sum(1 for v in violations if v.get("level") != "A")

        data = {
            "version_id": str(version.id) if version else None,
            "label": version.label if version else "Timetable Run",
            "status": run.status if run else (version.status if version else "COMPLETED"),
            "solver_time_ms": run.solver_time_ms if run else 0,
            "objective_value": run.objective_value if run else None,
            "total_sessions": len(version.sessions) if version else 0,
            "hard_violations": hard_count,
            "soft_violations": soft_count,
            "violations": violations,
            "diagnostic_notes": run.diagnostic_notes if run else "",
        }

    return provider.explain("generation", data)


def explain_violations(
    version_id: str,
    db: Session,
) -> ExplanationResponse:
    """
    Generate an in-depth assessment of validator violations for a timetable version.
    """
    provider = get_llm_provider()
    version = db.query(TimetableVersion).filter(TimetableVersion.id == version_id).first()
    if not version:
        return provider.explain("violations", {"violations": []})

    violations_db = db.query(Violation).filter(Violation.version_id == version.id).all()
    violations = [
        {
            "rule_id": v.rule_id,
            "level": v.level,
            "severity": v.severity,
            "description": v.description,
            "affected_sessions": v.affected_sessions,
        }
        for v in violations_db
    ]

    data = {
        "version_id": str(version.id),
        "label": version.label,
        "violations": violations,
    }
    return provider.explain("violations", data)


def explain_comparison(
    version_a_id: str,
    version_b_id: str,
    db: Session,
) -> ExplanationResponse:
    """
    Generate a human-readable summary of differences between two timetable versions.
    """
    provider = get_llm_provider()
    diff = compare_versions(db, version_a_id, version_b_id, include_diffs=True)

    data = {
        "version_a_id": diff.version_a_id,
        "version_b_id": diff.version_b_id,
        "total_sessions_a": diff.total_sessions_a,
        "total_sessions_b": diff.total_sessions_b,
        "added": diff.added,
        "removed": diff.removed,
        "moved": diff.moved,
        "unchanged": diff.unchanged,
        "diff_count": len(diff.diffs),
    }

    return provider.explain("comparison", data)
