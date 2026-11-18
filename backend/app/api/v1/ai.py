"""
backend/app/api/v1/ai.py
EduPlus AI Timetable Maker — AI Assistant API Endpoints (RBAC Protected)

Endpoints:
- POST /api/v1/ai/interpret — Interpret natural language scheduling requests (Admin, Coordinator)
- POST /api/v1/ai/explain   — Plain-language explanation of timetable/validation results (Admin, Coordinator)
- GET  /api/v1/ai/status    — Current AI provider status and supported capabilities (Admin, Coordinator)
"""

from __future__ import annotations

import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.ai.explainer import (
    explain_comparison,
    explain_generation,
    explain_violations,
)
from backend.app.ai.interpreter import interpret_prompt
from backend.app.ai.provider import get_llm_provider
from backend.app.ai.schemas import (
    AIStatusResponse,
    ExplanationRequest,
    ExplanationResponse,
    InterpretationRequest,
    InterpretationResponse,
)
from backend.app.api.deps import (
    assert_department_access,
    get_db,
    require_roles,
)
from backend.app.models.security import UserAccount
from backend.app.models.timetable import TimetableVersion
from backend.app.services.audit import record_audit_event

logger = logging.getLogger("eduplus.ai.api")
router = APIRouter(prefix="/ai", tags=["AI Assistant"])


@router.post("/interpret", response_model=InterpretationResponse, status_code=status.HTTP_200_OK)
def interpret_nl_constraint(
    payload: InterpretationRequest,
    request: Request,
    current_user: UserAccount = Depends(require_roles("admin", "coordinator")),
    db: Session = Depends(get_db),
):
    """
    Parse a natural language coordinator scheduling request into structured constraints.
    Grounded against active PostgreSQL entities (faculty, rooms, academic years, divisions).
    """
    effective_dept_id = payload.department_id
    if current_user.role != "admin":
        if payload.department_id:
            try:
                assert_department_access(current_user, uuid.UUID(payload.department_id))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid department_id format.")
        elif current_user.department_id:
            effective_dept_id = str(current_user.department_id)

    try:
        response = interpret_prompt(
            prompt=payload.prompt,
            db=db,
            department_id=effective_dept_id,
            academic_year_id=payload.academic_year_id,
        )
        record_audit_event(
            db=db,
            action="AI_PROMPT_INTERPRETED",
            entity_type="AI_INTERPRETATION",
            user_id=current_user.id,
            payload={
                "department_id": effective_dept_id,
                "constraints_count": len(response.constraints),
                "can_apply": response.can_apply,
                "provider": response.provider_used,
            },
            request=request,
            commit=True,
        )
        return response
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error interpreting prompt: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI interpretation failed. Please verify input and try again.",
        )


@router.post("/explain", response_model=ExplanationResponse, status_code=status.HTTP_200_OK)
def explain_result(
    payload: ExplanationRequest,
    current_user: UserAccount = Depends(require_roles("admin", "coordinator")),
    db: Session = Depends(get_db),
):
    """
    Generate plain-language markdown explanations and insights for timetable results,
    conflict violations, or version comparisons (Admin & Coordinator only).
    """
    # Verify department isolation if referencing specific version IDs
    for vid_str in (payload.version_id, payload.version_a_id, payload.version_b_id):
        if vid_str:
            try:
                v_uuid = uuid.UUID(vid_str)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid version ID.")
            v = db.query(TimetableVersion).filter(TimetableVersion.id == v_uuid).first()
            if v:
                assert_department_access(current_user, v.department_id)

    try:
        if payload.explanation_type == "comparison" and payload.version_a_id and payload.version_b_id:
            return explain_comparison(payload.version_a_id, payload.version_b_id, db)
        elif payload.explanation_type == "violations" and payload.version_id:
            return explain_violations(payload.version_id, db)
        else:
            return explain_generation(payload.version_id, payload.run_id, db, payload.payload)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error generating AI explanation: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI explanation failed. Please try again later.",
        )


@router.get("/status", response_model=AIStatusResponse, status_code=status.HTTP_200_OK)
def get_ai_status(
    current_user: UserAccount = Depends(require_roles("admin", "coordinator")),
):
    """
    Return active AI provider name, online status, model name, and supported constraint types.
    """
    provider = get_llm_provider()
    return AIStatusResponse(
        provider=provider.name,
        is_available=provider.is_available,
        model_name=getattr(provider, "model_name", "deterministic-pattern-engine"),
        supported_constraints=[
            "teacher_unavailability (Hard)",
            "teacher_preference (Soft)",
            "practical_block (Hard)",
            "division_preference (Soft)",
            "gap_minimization (Soft)",
            "consecutive_limit (Soft)",
        ],
        capabilities=[
            "Natural-language prompt interpretation",
            "Database entity grounding & disambiguation",
            "Structured constraint preview & confirmation",
            "Grounded timetable generation explanation",
            "Validator violation analysis",
            "Version diff explanation",
        ],
    )
