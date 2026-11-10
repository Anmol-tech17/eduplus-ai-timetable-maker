"""
backend/app/ai/__init__.py
EduPlus AI Timetable Maker — AI Assistant Module
"""

from backend.app.ai.schemas import (
    ConstraintCategory,
    ConstraintLevel,
    InterpretedConstraint,
    InterpretationRequest,
    InterpretationResponse,
    ExplanationRequest,
    ExplanationResponse,
)
from backend.app.ai.provider import get_llm_provider
from backend.app.ai.interpreter import interpret_prompt
from backend.app.ai.explainer import explain_generation, explain_comparison

__all__ = [
    "ConstraintCategory",
    "ConstraintLevel",
    "InterpretedConstraint",
    "InterpretationRequest",
    "InterpretationResponse",
    "ExplanationRequest",
    "ExplanationResponse",
    "get_llm_provider",
    "interpret_prompt",
    "explain_generation",
    "explain_comparison",
]
