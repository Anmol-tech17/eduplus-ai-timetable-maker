"""
backend/app/api/v1/ai.py
EduPlus AI Timetable Maker — AI Assistant API Endpoints

Endpoints:
- POST /api/v1/ai/interpret — Interpret natural language scheduling requests
- POST /api/v1/ai/explain   — Plain-language explanation of timetable/validation results
- GET  /api/v1/ai/status    — Current AI provider status and supported capabilities
"""

from __future__ import annotations

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
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
from backend.app.api.deps import get_db

logger = logging.getLogger("eduplus.ai.api")
router = APIRouter(prefix="/ai", tags=["AI Assistant"])


@router.post("/interpret", response_model=InterpretationResponse, status_code=status.HTTP_200_OK)
def interpret_nl_constraint(
    request: InterpretationRequest,
    db: Session = Depends(get_db),
):
    """
    Parse a natural language coordinator scheduling request into structured constraints.
    Grounded against active PostgreSQL entities (faculty, rooms, academic years, divisions).
    """
    try:
        response = interpret_prompt(
            prompt=request.prompt,
            db=db,
            department_id=request.department_id,
            academic_year_id=request.academic_year_id,
        )
        return response
    except Exception as exc:
        logger.error(f"Error interpreting prompt: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI interpretation failed: {str(exc)}",
        )


@router.post("/explain", response_model=ExplanationResponse, status_code=status.HTTP_200_OK)
def explain_result(
    request: ExplanationRequest,
    db: Session = Depends(get_db),
):
    """
    Generate plain-language markdown explanations and insights for timetable results,
    conflict violations, or version comparisons.
    """
    try:
        if request.explanation_type == "comparison" and request.version_a_id and request.version_b_id:
            return explain_comparison(request.version_a_id, request.version_b_id, db)
        elif request.explanation_type == "violations" and request.version_id:
            return explain_violations(request.version_id, db)
        else:
            return explain_generation(request.version_id, request.run_id, db, request.payload)
    except Exception as exc:
        logger.error(f"Error generating AI explanation: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI explanation failed: {str(exc)}",
        )


@router.get("/status", response_model=AIStatusResponse, status_code=status.HTTP_200_OK)
def get_ai_status():
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
