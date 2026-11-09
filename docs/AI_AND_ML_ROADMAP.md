# EduPlus — AI and ML Roadmap

> **Document ID:** AI_AND_ML_ROADMAP  
> **Version:** 0.1

---

## 1. Principle

The scheduling system is constraint-based and deterministic. AI and ML components are supplementary tools that **assist** with explanations, query interpretation, and complex reasoning — they do not control scheduling correctness.

**The constraint solver determines feasibility. The independent validator verifies it. The administrator controls publication. AI/ML components assist with communication and query resolution only.**

---

## 2. What the LLM May Do

| Permitted | Rationale |
|-----------|-----------|
| Parse natural-language query intent | Convert "when is my next class?" to a structured database query |
| Generate plain-language explanations from structured conflict data | Improve readability of validator output |
| Suggest alternative time slots (from solver output, not invented) | Communicate solver suggestions to users |
| Summarize timetable changes after a repair | Translate structured diff to human language |
| Answer FAQ-style queries from a vetted knowledge base | Non-scheduling administrative questions |

---

## 3. What the LLM Must Not Do

| Prohibited | Reason |
|-----------|--------|
| Place sessions in the timetable | Scheduling correctness requires CP-SAT + validator |
| Determine whether a timetable is valid | Only the independent validator may do this |
| Approve policy relaxations | Authorization is an administrative decision |
| Invent facts about teacher availability, rooms, or enrollments | Data must come from the database |
| Receive individual student names or IDs | Privacy — group-level data only |
| Override or bypass any constraint rule | Level A cannot be bypassed by any component |
| Claim to have solved a scheduling problem it did not solve | Honesty requirement |

---

## 4. Future ML Query Services

Student and teacher scheduling queries will eventually be handled by dedicated problem-solving ML models or model-based services, **not a general-purpose LLM**. This is a deliberate architectural direction.

### Query Categories and Planned Routing

| Query Type | Planned Handler | Phase |
|-----------|----------------|-------|
| "When is my next class?" | Database query (deterministic) | Phase 4 |
| "Which room is free on Thursday at 10am?" | Constraint engine query | Phase 4 |
| "Why was this session moved?" | Repair audit log lookup | Phase 6 |
| "Can this teacher cover a substitution?" | Availability + workload check via constraint engine | Phase 4 |
| "Why couldn't the scheduler place this session?" | Pre-solve diagnostic explanation | Phase 5 |
| "Find an alternative slot for this lab" | Repair solver query | Phase 6 |
| Complex natural-language scheduling question | ML query model (future) | Phase 8+ |

### Current Demo Behavior
- Student and teacher query submission is **mocked**.
- Queries are logged locally.
- No automated response is generated.
- The UI clearly states: "Query solving via ML model is planned for a future phase."

---

## 5. Structured Input/Output Contracts

All AI gateway inputs and outputs must conform to validated schemas. No raw user input is passed to an LLM without structuring and sanitization.

### Query Input Contract (Planned)
```json
{
  "query_id": "SQ001",
  "category": "timetable_lookup",
  "structured_intent": {
    "entity": "next_class",
    "context": {
      "student_group_id": "DIV_3A",
      "batch_id": "B1",
      "enrollment_group_id": "EG_CV",
      "current_datetime": "2026-10-21T10:30:00"
    }
  }
}
```

**Note:** No individual student name or ID is included. The context uses group-level identifiers only.

### Query Output Contract (Planned)
```json
{
  "query_id": "SQ001",
  "answer_type": "deterministic_db",
  "answer": {
    "subject": "ML Lab Practical",
    "start": "14:00",
    "end": "16:00",
    "day": "Wednesday",
    "room": "AI/ML Lab 1",
    "teacher": "Prof. Arjun Mehta"
  },
  "confidence": 1.0,
  "source": "published_timetable_v1"
}
```

---

## 6. Model Provider Abstraction

The AI gateway must use a provider-independent interface so that the underlying model can be swapped (GPT-4o, Gemini, Claude, open-source model) without changing the routing logic.

```python
# Planned interface
class AIGateway:
    def parse_query_intent(self, raw_text: str, context: dict) -> StructuredIntent: ...
    def generate_explanation(self, violation: ViolationRecord) -> str: ...
    def summarize_changes(self, session_changes: list[SessionChange]) -> str: ...
```

---

## 7. Privacy Considerations

- Individual student names, IDs, and enrollment records must never be sent to external AI APIs.
- Group-level identifiers (e.g., `DIV_3A`, `EG_CV`) are permitted.
- All AI gateway calls must be logged with input hash and model version.
- The institution must consent to the use of any cloud AI provider.
- An on-premises or private deployment option must be considered.

---

## 8. Evaluation and Testing Strategy

Before any ML query model goes live:
1. Offline evaluation against a test set of 100+ representative queries.
2. Accuracy measurement against ground-truth database answers.
3. Adversarial testing: queries designed to elicit scheduling decisions or rule violations.
4. Latency testing: query response must be < 3 seconds for deterministic queries.
5. Privacy audit: confirm no PII leaves the trust boundary.
6. Hallucination testing: confirm the model does not invent unavailable rooms, teachers, or sessions.

---

## 9. Integration Roadmap

| Phase | Milestone |
|-------|---------|
| Phase 0 (current) | Query submission UI only; no backend processing |
| Phase 2 | Query logging in database |
| Phase 4 | Deterministic DB query handler for common questions |
| Phase 5 | Structured conflict explanation using validator output |
| Phase 6 | Repair audit explanation (why sessions changed) |
| Phase 8 | AI gateway + ML query model for complex questions |
| Phase 9 | Provider-independent model swapping; on-premises option |
