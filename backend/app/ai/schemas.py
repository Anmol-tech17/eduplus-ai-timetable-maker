"""
backend/app/ai/schemas.py
EduPlus AI Timetable Maker — Pydantic Schemas for AI Assistant & NLP Interpretation
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ConstraintCategory(str, Enum):
    TEACHER_UNAVAILABILITY = "teacher_unavailability"
    TEACHER_PREFERENCE = "teacher_preference"
    PRACTICAL_BLOCK = "practical_block"
    DIVISION_PREFERENCE = "division_preference"
    GAP_MINIMIZATION = "gap_minimization"
    CONSECUTIVE_LIMIT = "consecutive_limit"
    ROOM_ALLOCATION = "room_allocation"
    UNSUPPORTED = "unsupported"


class ConstraintLevel(str, Enum):
    HARD = "HARD"
    SOFT = "SOFT"


class TargetType(str, Enum):
    TEACHER = "teacher"
    SUBJECT = "subject"
    DIVISION = "division"
    BATCH = "batch"
    ROOM = "room"
    GLOBAL = "global"


class InterpretedConstraint(BaseModel):
    """A single structured constraint extracted from natural language input."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category: ConstraintCategory
    level: ConstraintLevel = ConstraintLevel.HARD
    target_type: TargetType = TargetType.GLOBAL
    target_id: Optional[str] = None
    target_name: Optional[str] = None
    day_names: List[str] = Field(default_factory=list, description="Days where constraint applies (e.g. ['Monday']). Empty means all active days.")
    slot_indices: List[int] = Field(default_factory=list, description="1-based slot indices (e.g. [7, 8, 9, 10] for afternoon).")
    time_range_desc: Optional[str] = Field(default=None, description="Human description e.g. 'after 2 PM' or 'morning slots'")
    description: str = Field(..., description="Clear explanation of the interpreted constraint.")
    is_supported: bool = Field(default=True, description="Whether CP-SAT solver natively supports this constraint.")
    support_rationale: Optional[str] = Field(default=None, description="Explanation if constraint is unsupported or partially supported.")
    is_ambiguous: bool = Field(default=False, description="True if entity or intent could not be unambiguously resolved.")
    clarification_needed: Optional[str] = Field(default=None, description="Follow-up question or resolution required before applying.")


class ClarificationQuestion(BaseModel):
    """Question posed to user when prompt has missing or ambiguous entities."""
    field: str
    message: str
    options: List[str] = Field(default_factory=list)


class InterpretationRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=1000, description="Natural language scheduling instruction.")
    department_id: Optional[str] = Field(default=None, description="Department context for entity resolution.")
    academic_year_id: Optional[str] = Field(default=None, description="Academic year context if specific.")


class InterpretationResponse(BaseModel):
    raw_prompt: str
    summary: str
    scope_department_id: Optional[str] = None
    constraints: List[InterpretedConstraint] = Field(default_factory=list)
    clarifications: List[ClarificationQuestion] = Field(default_factory=list)
    can_apply: bool = Field(default=True, description="True if all constraints are supported and unambiguous.")
    provider_used: str = "mock"


class ExplanationRequest(BaseModel):
    explanation_type: str = Field(
        default="generation",
        description="Type of explanation: 'generation', 'violations', 'comparison', or 'infeasibility'."
    )
    version_id: Optional[str] = Field(default=None, description="Timetable version ID to explain.")
    run_id: Optional[str] = Field(default=None, description="Generation run ID to explain.")
    version_a_id: Optional[str] = Field(default=None, description="Base version for comparison.")
    version_b_id: Optional[str] = Field(default=None, description="Target version for comparison.")
    payload: Optional[Dict[str, Any]] = Field(default=None, description="Optional raw payload or context.")


class ExplanationResponse(BaseModel):
    summary_markdown: str
    key_insights: List[str] = Field(default_factory=list)
    actionable_recommendations: List[str] = Field(default_factory=list)
    provider_used: str = "mock"


class AIStatusResponse(BaseModel):
    provider: str
    is_available: bool
    model_name: str
    supported_constraints: List[str]
    capabilities: List[str]
