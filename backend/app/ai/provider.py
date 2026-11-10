"""
backend/app/ai/provider.py
EduPlus AI Timetable Maker — LLM Provider Abstraction & Implementations

Provides:
- BaseLLMProvider: Abstract interface.
- MockLLMProvider: Offline, deterministic regex/entity parsing and grounded explanations.
- GeminiLLMProvider: Live Google Gemini API connector using httpx.
- get_llm_provider: Factory returning the appropriate provider.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import httpx

from backend.app.ai.schemas import (
    ClarificationQuestion,
    ConstraintCategory,
    ConstraintLevel,
    InterpretedConstraint,
    InterpretationResponse,
    ExplanationResponse,
    TargetType,
)
from backend.app.core.config import settings

logger = logging.getLogger("eduplus.ai.provider")


class BaseLLMProvider(ABC):
    """Abstract base class for all LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the provider (e.g. 'mock', 'gemini')."""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Whether the provider is configured and available."""
        pass

    @abstractmethod
    def interpret(self, prompt: str, context: Dict[str, Any]) -> InterpretationResponse:
        """Parse natural language scheduling instructions into structured constraints."""
        pass

    @abstractmethod
    def explain(self, explanation_type: str, data: Dict[str, Any]) -> ExplanationResponse:
        """Generate plain-language explanations from structured timetable/validation data."""
        pass


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic, offline LLM provider.
    Evaluates institutional pattern rules, extracts grounded database entities,
    flags ambiguities, and produces evidence-grounded markdown explanations.
    Requires zero network requests and guarantees 100% test reliability.
    """

    @property
    def name(self) -> str:
        return "mock"

    @property
    def is_available(self) -> bool:
        return True

    # -------------------------------------------------------------------------
    # Interpretation Engine
    # -------------------------------------------------------------------------
    def interpret(self, prompt: str, context: Dict[str, Any]) -> InterpretationResponse:
        prompt_lower = prompt.lower().strip()
        constraints: List[InterpretedConstraint] = []
        clarifications: List[ClarificationQuestion] = []

        teachers: List[Dict[str, Any]] = context.get("teachers", [])
        time_slots: List[Dict[str, Any]] = context.get("time_slots", [])
        working_days: List[str] = context.get("working_days", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
        academic_years: List[Dict[str, Any]] = context.get("academic_years", [])
        divisions: List[Dict[str, Any]] = context.get("divisions", [])

        # 1. Unsupported Requests Check
        unsupported_keywords = [
            ("work from home", "Faculty remote work policies are institutional administrative rules not managed by timetable scheduling."),
            ("free lunch", "Catering and meal benefits are outside institutional timetable allocation."),
            ("snacks", "Refreshments and canteen provisions are outside scheduling parameters."),
            ("parking", "Campus parking allocations are handled by facilities management, not academic timetabling."),
            ("automatic grades", "Grading policies are controlled by the examination board."),
        ]
        for kw, reason in unsupported_keywords:
            if kw in prompt_lower:
                constraints.append(
                    InterpretedConstraint(
                        category=ConstraintCategory.UNSUPPORTED,
                        level=ConstraintLevel.SOFT,
                        target_type=TargetType.GLOBAL,
                        description=f"Request to '{kw}' is not an institutional scheduling constraint.",
                        is_supported=False,
                        support_rationale=reason,
                    )
                )

        # 2. Check for Unknown Teacher Mentions (Ambiguity / Grounding)
        # Look for "prof." or "dr." or "professor" followed by a name
        teacher_mentions = re.findall(r"(?:dr\.|prof\.|professor)\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)?)", prompt, re.IGNORECASE)
        for mention in teacher_mentions:
            mention_cleaned = mention.strip().lower()
            matched_teacher = None
            for t in teachers:
                t_name_lower = t["name"].lower()
                t_short_lower = t.get("short_name", "").lower()
                if mention_cleaned in t_name_lower or mention_cleaned in t_short_lower:
                    matched_teacher = t
                    break

            if not matched_teacher:
                clarifications.append(
                    ClarificationQuestion(
                        field="teacher_name",
                        message=f"Teacher '{mention}' was not found in the department directory. Please select the intended faculty member:",
                        options=[t["name"] for t in teachers[:5]],
                    )
                )
                constraints.append(
                    InterpretedConstraint(
                        category=ConstraintCategory.TEACHER_UNAVAILABILITY,
                        level=ConstraintLevel.HARD,
                        target_type=TargetType.TEACHER,
                        target_id=None,
                        target_name=mention,
                        description=f"Unavailability requested for unknown teacher '{mention}'.",
                        is_supported=True,
                        is_ambiguous=True,
                        clarification_needed=f"Entity '{mention}' could not be matched to an active teacher in this department.",
                    )
                )

        # 3. Teacher Unavailability Constraints (e.g. "no classes after 2 PM" or "unavailable on Friday")
        # Match time range (e.g. "after 2 pm", "after 14:00", "after 12", "before 10 am")
        time_match = re.search(r"after\s+(2\s*(?:pm)?|14(?::00)?|12(?::00)?|13(?::00)?)", prompt_lower)
        if time_match:
            time_str = time_match.group(1).replace(" ", "")
            if "2" in time_str or "14" in time_str:
                # Slots after 14:00 -> TS7 (14:00-15:00), TS8 (15:00-16:00), TS9 (16:00-17:00), TS10 (17:00-18:00)
                affected_slots = [7, 8, 9, 10]
                time_desc = "after 2:00 PM (Slots 7–10: 14:00–18:00)"
            elif "12" in time_str:
                affected_slots = [5, 6, 7, 8, 9, 10]
                time_desc = "after 12:00 PM (Slots 5–10: 12:00–18:00)"
            else:
                affected_slots = [7, 8, 9, 10]
                time_desc = "after 2:00 PM"

            # Check which teacher is referenced (ignoring honorifics like Dr. / Prof.)
            matched_teachers = []
            for t in teachers:
                clean_name = re.sub(r"^(?:dr\.|prof\.|professor)\s*", "", t["name"], flags=re.IGNORECASE).strip().lower()
                parts = clean_name.split()
                first_name = parts[0] if parts else ""
                last_name = parts[-1] if len(parts) > 1 else first_name

                if (
                    clean_name in prompt_lower
                    or (last_name and len(last_name) > 3 and last_name in prompt_lower)
                    or (first_name and len(first_name) > 3 and first_name in prompt_lower)
                    or (t.get("short_name", "").lower() in prompt_lower)
                ):
                    matched_teachers.append(t)

            if matched_teachers:
                for mt in matched_teachers:
                    constraints.append(
                        InterpretedConstraint(
                            category=ConstraintCategory.TEACHER_UNAVAILABILITY,
                            level=ConstraintLevel.HARD,
                            target_type=TargetType.TEACHER,
                            target_id=mt["id"],
                            target_name=mt["name"],
                            day_names=working_days,
                            slot_indices=affected_slots,
                            time_range_desc=time_desc,
                            description=f"Block {mt['name']} from teaching {time_desc} across all active weekdays.",
                            is_supported=True,
                        )
                    )

        # Unavailability on specific days (e.g. "unavailable on Friday")
        day_match = re.search(r"(?:unavailable|no classes|off)\s+on\s+(monday|tuesday|wednesday|thursday|friday|saturday)", prompt_lower)
        if day_match:
            day_name = day_match.group(1).capitalize()
            matched_teachers = []
            for t in teachers:
                clean_name = re.sub(r"^(?:dr\.|prof\.|professor)\s*", "", t["name"], flags=re.IGNORECASE).strip().lower()
                parts = clean_name.split()
                first_name = parts[0] if parts else ""
                last_name = parts[-1] if len(parts) > 1 else first_name
                if clean_name in prompt_lower or (last_name and len(last_name) > 3 and last_name in prompt_lower) or (first_name and len(first_name) > 3 and first_name in prompt_lower):
                    matched_teachers.append(t)

            for mt in matched_teachers:
                constraints.append(
                    InterpretedConstraint(
                        category=ConstraintCategory.TEACHER_UNAVAILABILITY,
                        level=ConstraintLevel.HARD,
                        target_type=TargetType.TEACHER,
                        target_id=mt["id"],
                        target_name=mt["name"],
                        day_names=[day_name],
                        slot_indices=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                        time_range_desc=f"Full day ({day_name})",
                        description=f"Mark {mt['name']} as unavailable on all slots of {day_name}.",
                        is_supported=True,
                    )
                )

        # 4. Practical Block on Specific Day (e.g. "avoid practicals on Monday" or "avoid scheduling practicals on Monday")
        practical_day_match = re.search(r"(?:avoid|no|do not schedule|prevent|restrict)(?:\s+scheduling)?\s+(?:practical|practicals|labs?)\s+on\s+(monday|tuesday|wednesday|thursday|friday|saturday)", prompt_lower)
        if practical_day_match:
            day_name = practical_day_match.group(1).capitalize()
            constraints.append(
                InterpretedConstraint(
                    category=ConstraintCategory.PRACTICAL_BLOCK,
                    level=ConstraintLevel.HARD,
                    target_type=TargetType.GLOBAL,
                    day_names=[day_name],
                    slot_indices=[],
                    description=f"Prevent scheduling 2-hour practical laboratory sessions on {day_name}.",
                    is_supported=True,
                )
            )

        # 5. Morning Preferences (e.g. "prefer morning slots for third-year AIML" or "prefer morning slots for Dr. Priya")
        if "prefer morning" in prompt_lower or "morning slots" in prompt_lower:
            # Check if for teacher or for academic year/division
            matched_teacher = None
            for t in teachers:
                clean_name = re.sub(r"^(?:dr\.|prof\.|professor)\s*", "", t["name"], flags=re.IGNORECASE).strip().lower()
                parts = clean_name.split()
                first_name = parts[0] if parts else ""
                last_name = parts[-1] if len(parts) > 1 else first_name
                if clean_name in prompt_lower or (last_name and len(last_name) > 3 and last_name in prompt_lower) or (first_name and len(first_name) > 3 and first_name in prompt_lower):
                    matched_teacher = t
                    break

            matched_year = next((ay for ay in academic_years if str(ay.get("year_number")) in prompt_lower or ay.get("label", "").lower() in prompt_lower or "third" in prompt_lower and ay.get("year_number") == 3), None)

            if matched_teacher:
                constraints.append(
                    InterpretedConstraint(
                        category=ConstraintCategory.TEACHER_PREFERENCE,
                        level=ConstraintLevel.SOFT,
                        target_type=TargetType.TEACHER,
                        target_id=matched_teacher["id"],
                        target_name=matched_teacher["name"],
                        day_names=working_days,
                        slot_indices=[1, 2, 3, 4],
                        time_range_desc="Morning (Slots 1–4: 08:00–12:00)",
                        description=f"Reward morning slot placement (08:00–12:00) for {matched_teacher['name']} in CP-SAT objective.",
                        is_supported=True,
                    )
                )
            elif matched_year:
                constraints.append(
                    InterpretedConstraint(
                        category=ConstraintCategory.DIVISION_PREFERENCE,
                        level=ConstraintLevel.SOFT,
                        target_type=TargetType.DIVISION,
                        target_id=matched_year.get("id"),
                        target_name=matched_year.get("label", "Year " + str(matched_year.get("year_number"))),
                        day_names=working_days,
                        slot_indices=[1, 2, 3, 4],
                        time_range_desc="Morning (Slots 1–4: 08:00–12:00)",
                        description=f"Encourage morning scheduling for {matched_year.get('label', 'Third Year')} sessions.",
                        is_supported=True,
                    )
                )
            else:
                # Global morning preference
                constraints.append(
                    InterpretedConstraint(
                        category=ConstraintCategory.TEACHER_PREFERENCE,
                        level=ConstraintLevel.SOFT,
                        target_type=TargetType.GLOBAL,
                        day_names=working_days,
                        slot_indices=[1, 2, 3, 4],
                        time_range_desc="Morning (Slots 1–4: 08:00–12:00)",
                        description="Prioritize scheduling theory sessions in morning time slots across divisions.",
                        is_supported=True,
                    )
                )

        # 6. Idle Gap Minimization (e.g. "fewer gaps", "minimize idle gaps", "compact timetable")
        if any(kw in prompt_lower for kw in ["fewer gaps", "minimize gaps", "idle gap", "compact timetable", "reduce gaps"]):
            constraints.append(
                InterpretedConstraint(
                    category=ConstraintCategory.GAP_MINIMIZATION,
                    level=ConstraintLevel.SOFT,
                    target_type=TargetType.GLOBAL,
                    description="Increase CP-SAT gap penalty weight (S2) to compact teacher and division schedules.",
                    is_supported=True,
                )
            )

        # 7. Consecutive Session Limit (e.g. "maximum 2 consecutive", "limit consecutive lectures")
        if any(kw in prompt_lower for kw in ["consecutive", "back to back", "continuous lectures"]):
            constraints.append(
                InterpretedConstraint(
                    category=ConstraintCategory.CONSECUTIVE_LIMIT,
                    level=ConstraintLevel.SOFT,
                    target_type=TargetType.GLOBAL,
                    description="Enforce penalty for teaching loads exceeding 2–3 consecutive slots.",
                    is_supported=True,
                )
            )

        # Summary construction
        num_hard = sum(1 for c in constraints if c.level == ConstraintLevel.HARD and c.is_supported and not c.is_ambiguous)
        num_soft = sum(1 for c in constraints if c.level == ConstraintLevel.SOFT and c.is_supported)
        num_unsupported = sum(1 for c in constraints if not c.is_supported)
        num_ambiguous = sum(1 for c in constraints if c.is_ambiguous)

        if not constraints:
            summary = "No actionable scheduling constraints were identified in the instruction."
            can_apply = False
        else:
            summary = (
                f"Identified {len(constraints)} constraint(s): {num_hard} hard rule(s), "
                f"{num_soft} soft preference(s)"
            )
            if num_unsupported > 0:
                summary += f", {num_unsupported} unsupported item(s)"
            if num_ambiguous > 0:
                summary += f", {num_ambiguous} ambiguous item(s) requiring clarification"
            summary += "."
            can_apply = (num_ambiguous == 0 and num_unsupported == 0 and len(clarifications) == 0)

        return InterpretationResponse(
            raw_prompt=prompt,
            summary=summary,
            scope_department_id=context.get("department_id"),
            constraints=constraints,
            clarifications=clarifications,
            can_apply=can_apply,
            provider_used=self.name,
        )

    # -------------------------------------------------------------------------
    # Explanation Engine
    # -------------------------------------------------------------------------
    def explain(self, explanation_type: str, data: Dict[str, Any]) -> ExplanationResponse:
        if explanation_type == "generation":
            return self._explain_generation(data)
        elif explanation_type == "violations":
            return self._explain_violations(data)
        elif explanation_type == "comparison":
            return self._explain_comparison(data)
        elif explanation_type == "infeasibility":
            return self._explain_infeasibility(data)
        else:
            return self._explain_general(data)

    def _explain_generation(self, data: Dict[str, Any]) -> ExplanationResponse:
        status = data.get("status", "FEASIBLE")
        total_sessions = data.get("total_sessions", 0)
        solver_time_ms = data.get("solver_time_ms", 0)
        objective_value = data.get("objective_value")
        hard_violations = data.get("hard_violations", 0)
        soft_violations = data.get("soft_violations", 0)
        label = data.get("label", "Timetable Candidate")

        insights = [
            f"Solver concluded with status **{status}** in {solver_time_ms} ms.",
            f"Successfully scheduled **{total_sessions} total class sessions**.",
        ]
        if objective_value is not None:
            insights.append(f"Solution quality objective score: **{objective_value:.1f}**.")

        recs = []
        if hard_violations == 0:
            insights.append("Zero Level A (Hard) violations: schedule is 100% operationally valid.")
            recs.append("Candidate satisfies all hard constraints and is eligible for coordinator publication.")
        else:
            insights.append(f"Detected **{hard_violations} hard violation(s)** that must be resolved.")
            recs.append("Review Level A conflict list before publishing.")

        if soft_violations > 0:
            recs.append(f"Identified {soft_violations} soft preference trade-off(s) (e.g. idle gaps or non-preferred slots).")

        md = f"""### AI Timetable Analysis: {label}

The CP-SAT scheduling solver generated this schedule in **{solver_time_ms / 1000:.2f} seconds** with status **{status}**.
All **{total_sessions} required lecture and practical sessions** were allocated into weekly slots.

- **Hard Constraints:** {'✅ Satisfied (0 conflicts)' if hard_violations == 0 else f'⚠️ {hard_violations} violations found'}
- **Soft Objectives:** {'✅ High compactness' if soft_violations == 0 else f'{soft_violations} minor preference trade-offs'}
"""
        return ExplanationResponse(
            summary_markdown=md.strip(),
            key_insights=insights,
            actionable_recommendations=recs,
            provider_used=self.name,
        )

    def _explain_violations(self, data: Dict[str, Any]) -> ExplanationResponse:
        violations = data.get("violations", [])
        hard_v = [v for v in violations if v.get("level") == "A"]
        policy_v = [v for v in violations if v.get("level") == "B"]
        soft_v = [v for v in violations if v.get("level") == "C"]

        insights = [
            f"Independent validator evaluated schedule: found {len(hard_v)} hard (Level A), {len(policy_v)} policy (Level B), and {len(soft_v)} soft (Level C) items.",
        ]
        recs = []

        if hard_v:
            for v in hard_v[:3]:
                recs.append(f"**Resolve {v.get('rule_id', 'Conflict')}:** {v.get('description', '')}")
        else:
            recs.append("All hard operational rules (A01–A10) are fully satisfied.")

        if soft_v:
            recs.append("Soft preferences can be improved by re-running with higher gap or consecutive penalty weights.")

        md = f"""### Validator Conflict Assessment

The deterministic validation engine verified this candidate against institutional rules:
- **Level A (Hard Constraints):** {len(hard_v)}
- **Level B (Institutional Policies):** {len(policy_v)}
- **Level C (Preferences):** {len(soft_v)}

{'⛔ **Publication Gate Blocked:** Level A violations prevent this schedule from being published.' if hard_v else '✅ **Publication Gate Clear:** No Level A violations detected.'}
"""
        return ExplanationResponse(
            summary_markdown=md.strip(),
            key_insights=insights,
            actionable_recommendations=recs,
            provider_used=self.name,
        )

    def _explain_comparison(self, data: Dict[str, Any]) -> ExplanationResponse:
        total_a = data.get("total_sessions_a", 0)
        total_b = data.get("total_sessions_b", 0)
        added = data.get("added", 0)
        removed = data.get("removed", 0)
        moved = data.get("moved", 0)
        unchanged = data.get("unchanged", 0)

        insights = [
            f"Comparison between Base Version ({total_a} sessions) and Compared Version ({total_b} sessions).",
            f"**{unchanged} sessions remained unchanged** (stability rate: {unchanged / max(total_a, 1) * 100:.1f}%).",
            f"**{moved} sessions were relocated** to different slots or rooms.",
        ]
        if added > 0:
            insights.append(f"**{added} new sessions** were introduced.")
        if removed > 0:
            insights.append(f"**{removed} sessions** were deleted or unassigned.")

        recs = [
            "Notify faculty members whose session times or rooms changed.",
            "Verify laboratory room assignments for moved practical sessions.",
        ]

        md = f"""### Version Comparison Summary

The schedule evolution between Version A and Version B resulted in:
- **Unchanged Sessions:** {unchanged}
- **Moved Sessions:** {moved}
- **Added Sessions:** {added}
- **Removed Sessions:** {removed}

This indicates a **{'low-disruption localized update' if moved < 10 else 'broad schedule restructuring'}**.
"""
        return ExplanationResponse(
            summary_markdown=md.strip(),
            key_insights=insights,
            actionable_recommendations=recs,
            provider_used=self.name,
        )

    def _explain_infeasibility(self, data: Dict[str, Any]) -> ExplanationResponse:
        diagnostic = data.get("diagnostic_notes", "No feasible timetable could be scheduled with the current constraints.")
        insights = [
            "The CP-SAT solver proved that the current combination of hard constraints is mathematically infeasible.",
            "Primary bottlenecks typically include teacher availability blocks, room capacity mismatches, or conflicting multi-slot practical sessions.",
        ]
        recs = [
            "Inspect teacher availability blocks (H7) — ensure teachers are available for enough slots to meet their weekly workload.",
            "Check laboratory room capacities against batch sizes (H8).",
            "Relax conflicting natural language constraints and re-attempt generation.",
        ]
        md = f"""### Infeasibility Root-Cause Diagnosis

The solver reported **INFEASIBLE**:
> {diagnostic}

No timetable exists that satisfies all active Level A hard constraints simultaneously.
"""
        return ExplanationResponse(
            summary_markdown=md.strip(),
            key_insights=insights,
            actionable_recommendations=recs,
            provider_used=self.name,
        )

    def _explain_general(self, data: Dict[str, Any]) -> ExplanationResponse:
        text = data.get("text", "General institutional timetable analysis.")
        return ExplanationResponse(
            summary_markdown=text,
            key_insights=["Institutional AI assistance operates in hybrid tandem with CP-SAT."],
            actionable_recommendations=["Review solver diagnostics for authoritative results."],
            provider_used=self.name,
        )


class GeminiLLMProvider(BaseLLMProvider):
    """
    Live Google Gemini LLM provider.
    Uses Google's Gemini REST API when GEMINI_API_KEY / GOOGLE_API_KEY is configured.
    Falls back gracefully to MockLLMProvider on network timeout, rate limit, or offline state.
    """

    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash") -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.fallback = MockLLMProvider()

    @property
    def name(self) -> str:
        return f"gemini ({self.model_name})"

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    def interpret(self, prompt: str, context: Dict[str, Any]) -> InterpretationResponse:
        if not self.is_available:
            return self.fallback.interpret(prompt, context)

        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        system_instruction = (
            "You are the AI Timetable Assistant for EduPlus, an institutional timetable software. "
            "Your task is to parse a natural language scheduling instruction from a coordinator into structured constraints. "
            "You must ground all entities (teachers, departments, academic years, subjects, rooms) strictly against the provided context. "
            "Do NOT invent teacher names or IDs. If a teacher or entity cannot be found, flag it as is_ambiguous=True with a clarification question. "
            "Output valid JSON conforming to the following schema:\n"
            "{\n"
            '  "raw_prompt": string,\n'
            '  "summary": string,\n'
            '  "constraints": [\n'
            "    {\n"
            '      "category": "teacher_unavailability" | "teacher_preference" | "practical_block" | "division_preference" | "gap_minimization" | "consecutive_limit" | "unsupported",\n'
            '      "level": "HARD" | "SOFT",\n'
            '      "target_type": "teacher" | "subject" | "division" | "batch" | "room" | "global",\n'
            '      "target_id": string or null,\n'
            '      "target_name": string or null,\n'
            '      "day_names": [string],\n'
            '      "slot_indices": [integer],\n'
            '      "time_range_desc": string or null,\n'
            '      "description": string,\n'
            '      "is_supported": boolean,\n'
            '      "support_rationale": string or null,\n'
            '      "is_ambiguous": boolean,\n'
            '      "clarification_needed": string or null\n'
            "    }\n"
            "  ],\n"
            '  "clarifications": [\n'
            '    {"field": string, "message": string, "options": [string]}\n'
            "  ],\n"
            '  "can_apply": boolean\n'
            "}"
        )

        user_content = json.dumps({
            "prompt": prompt,
            "context": context,
        })

        payload = {
            "system_instruction": {"parts": [{"text": system_instruction}]},
            "contents": [{"parts": [{"text": user_content}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.1,
            },
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(endpoint, json=payload)
                if res.status_code == 200:
                    resp_json = res.json()
                    candidate_text = resp_json["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = json.loads(candidate_text)
                    parsed["provider_used"] = self.name
                    return InterpretationResponse(**parsed)
                else:
                    logger.warning(f"Gemini API returned status {res.status_code}: {res.text}. Falling back to mock.")
                    return self.fallback.interpret(prompt, context)
        except Exception as exc:
            logger.warning(f"Gemini API call failed ({exc}). Falling back to mock provider.")
            return self.fallback.interpret(prompt, context)

    def explain(self, explanation_type: str, data: Dict[str, Any]) -> ExplanationResponse:
        if not self.is_available:
            return self.fallback.explain(explanation_type, data)

        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        prompt = (
            f"You are the AI Timetable Assistant for EduPlus. Explain the following {explanation_type} data "
            "for academic coordinators in clear, grounded Markdown. Never invent facts outside the data. "
            "Return JSON with keys: summary_markdown (string), key_insights (list of strings), "
            "actionable_recommendations (list of strings).\n\n"
            f"Data: {json.dumps(data)}"
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.2,
            },
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(endpoint, json=payload)
                if res.status_code == 200:
                    candidate_text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = json.loads(candidate_text)
                    parsed["provider_used"] = self.name
                    return ExplanationResponse(**parsed)
                else:
                    return self.fallback.explain(explanation_type, data)
        except Exception as exc:
            logger.warning(f"Gemini API explain failed ({exc}). Falling back to mock.")
            return self.fallback.explain(explanation_type, data)


def get_llm_provider() -> BaseLLMProvider:
    """Factory returning the active LLM provider based on application configuration."""
    provider_pref = getattr(settings, "LLM_PROVIDER", "auto").lower()
    gemini_key = getattr(settings, "GEMINI_API_KEY", "")

    if provider_pref == "gemini" or (provider_pref == "auto" and gemini_key):
        model_name = getattr(settings, "GEMINI_MODEL", "gemini-1.5-flash")
        return GeminiLLMProvider(api_key=gemini_key, model_name=model_name)

    return MockLLMProvider()
