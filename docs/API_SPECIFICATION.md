# EduPlus — REST API Specification

> **Document ID:** API_SPECIFICATION  
> **Version:** 0.1  
> **Protocol:** REST over HTTPS / JSON  
> **Status:** Specification Baseline — Planned for Phase 1 & 2 Implementation  
> **Demo Notice:** The prototype demo simulates these endpoints via frontend mock handlers (`mockData.js`).  

---

## 1. Global Standards & Error Envelope

All API endpoints follow REST conventions and return JSON payloads. Authentication uses standard Bearer JWT tokens in the `Authorization` header.

### 1.1 Standard Error Format (RFC 7807)
```json
{
  "type": "https://api.eduplus.internal/errors/VALIDATION_FAILED",
  "title": "Timetable Validation Failed",
  "status": 422,
  "detail": "The candidate timetable violates Level A hard constraint A01 (Teacher Conflict).",
  "instance": "/api/v1/timetables/candidates/cand_101/publish",
  "invalid_params": [
    {
      "name": "sessions[14]",
      "reason": "Teacher 'Dr. Priya Sharma' is already scheduled at Tuesday TS3"
    }
  ],
  "timestamp": "2026-10-21T11:20:00Z"
}
```

### 1.2 HTTP Status Code Conventions
- `200 OK`: Successful synchronous retrieval or state change.
- `201 Created`: Resource successfully created.
- `202 Accepted`: Asynchronous background task queued (e.g., timetable solver run).
- `400 Bad Request`: Malformed JSON or invalid parameter syntax.
- `401 Unauthorized`: Missing, expired, or invalid JWT token.
- `403 Forbidden`: Authenticated user lacks permission for the resource.
- `404 Not Found`: Target entity does not exist.
- `409 Conflict`: Resource state conflict (e.g., trying to publish when already published).
- `422 Unprocessable Entity`: Business rule or validation constraint violation.
- `500 Internal Server Error`: Unhandled server exception.

---

## 2. Authentication & Session Endpoints

### 2.1 Login
- **Endpoint:** `POST /api/v1/auth/login`
- **Access:** Public
- **Status:** *Planned Backend* (Prototype uses frontend credential matching)

#### Request:
```json
{
  "email": "admin@eduplus.demo",
  "password": "admin123"
}
```

#### Response (`200 OK`):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
  "refresh_token": "def50200...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "user": {
    "id": "u001",
    "name": "Dr. Academic Dean",
    "email": "admin@eduplus.demo",
    "role": "admin",
    "department_id": "d001"
  }
}
```

### 2.2 Get Current User Profile
- **Endpoint:** `GET /api/v1/auth/me`
- **Access:** Authenticated (Any role)
- **Response (`200 OK`):** Returns profile matching token identity.

---

## 3. Academic Data Management (Admin Role)

### 3.1 List Subjects
- **Endpoint:** `GET /api/v1/academic/subjects`
- **Access:** `admin`, `teacher`
- **Query Params:** `department_id`, `year_number`, `is_elective`

### 3.2 List Teachers & Capacities
- **Endpoint:** `GET /api/v1/academic/teachers`
- **Access:** `admin`, `teacher`

### 3.3 List Rooms & Labs
- **Endpoint:** `GET /api/v1/academic/rooms`
- **Access:** `admin`, `teacher`

---

## 4. Timetable Generation & Solver Pipeline

### 4.1 Trigger Asynchronous Solver Run
- **Endpoint:** `POST /api/v1/timetables/generate`
- **Access:** `admin` only
- **Status:** *Planned Phase 3* (Prototype demo loads mock candidates)

#### Request:
```json
{
  "department_id": "d0000001-0000-0000-0000-000000000001",
  "academic_year_code": "2026-27",
  "semester": 1,
  "time_limit_seconds": 90,
  "max_candidates": 3,
  "random_seed": 42
}
```

#### Response (`202 Accepted`):
```json
{
  "job_id": "job_gen_98214",
  "status": "QUEUED",
  "estimated_time_seconds": 30,
  "status_url": "/api/v1/timetables/jobs/job_gen_98214"
}
```

### 4.2 Poll Generation Job Status
- **Endpoint:** `GET /api/v1/timetables/jobs/{job_id}`
- **Access:** `admin`

#### Response (`200 OK` when completed):
```json
{
  "job_id": "job_gen_98214",
  "status": "COMPLETED",
  "solver_time_ms": 4820,
  "solver_status": "FEASIBLE",
  "candidates": [
    {
      "candidate_id": "cand_01",
      "objective_score": 142.5,
      "violations_count": { "A": 0, "B": 0, "C": 4 }
    },
    {
      "candidate_id": "cand_02",
      "objective_score": 158.0,
      "violations_count": { "A": 0, "B": 1, "C": 2 }
    }
  ]
}
```

---

## 5. Candidate Validation & Publication

### 5.1 Run Independent Validation on Candidate
- **Endpoint:** `POST /api/v1/timetables/candidates/{id}/validate`
- **Access:** `admin`
- **Status:** *Planned Phase 2* (Demo performs in-browser validation against mock rules)

#### Response (`200 OK`):
```json
{
  "candidate_id": "cand_02",
  "is_publishable": false,
  "summary": {
    "level_a_errors": 1,
    "level_b_warnings": 1,
    "level_c_notices": 2
  },
  "violations": [
    {
      "rule_id": "A01",
      "rule_level": "A",
      "severity": "error",
      "description": "Dr. Priya Sharma is double-booked on Tuesday Slot 3 between Year 2 Div A and Year 3 Div B.",
      "affected_session_ids": ["s101", "s204"]
    }
  ]
}
```

### 5.2 Publish Candidate Timetable
- **Endpoint:** `POST /api/v1/timetables/candidates/{id}/publish`
- **Access:** `admin` only
- **Precondition:** Candidate must have 0 Level A violations and all Level B violations approved.

#### Request:
```json
{
  "version_label": "AY2026-27 Sem 1 - v1.0 Final",
  "policy_relaxation_reasons": []
}
```

#### Response (`200 OK`):
```json
{
  "published_version_id": "tt_ver_2026_sem1_v1",
  "version_number": 1,
  "status": "published",
  "published_at": "2026-10-21T11:25:00Z",
  "message": "Timetable published successfully. Student and teacher views updated."
}
```

---

## 6. Teacher Portal & Request Management

### 6.1 Get Teacher's Schedule
- **Endpoint:** `GET /api/v1/teacher/schedule`
- **Access:** `teacher`
- **Query Params:** `academic_year`, `semester`
- **Response (`200 OK`):** Returns filtered session array for the authenticated teacher.

### 6.2 Submit Schedule Change Request
- **Endpoint:** `POST /api/v1/teacher/requests`
- **Access:** `teacher`
- **Status:** *Implemented in demo state*

#### Request:
```json
{
  "request_type": "reschedule",
  "session_id": "s_101",
  "current_slot": "Tuesday TS3",
  "proposed_slot": "Thursday TS2",
  "reason": "Attending Faculty Development Programme"
}
```

#### Response (`201 Created`):
```json
{
  "request_id": "req_2026_09",
  "status": "pending",
  "submitted_at": "2026-10-21T11:27:00Z",
  "message": "Request submitted to Academic Coordinator."
}
```

### 6.3 Review Teacher Request (Admin Action)
- **Endpoint:** `PATCH /api/v1/admin/requests/{request_id}`
- **Access:** `admin` only
- **Request:** `{"action": "approved", "comment": "Approved substitute teacher PVS."}`
- **Response (`200 OK`):** Returns updated request record.

---

## 7. Student Portal & AI Query Service

### 7.1 Get Student's Schedule
- **Endpoint:** `GET /api/v1/student/schedule`
- **Access:** `student`
- **Query Params:** `division_id`, `batch_id`, `elective_group_ids`
- **Response (`200 OK`):** Complete weekly grid matching student's enrolled cohort and electives.

### 7.2 Natural Language Timetable Query
- **Endpoint:** `POST /api/v1/ai/query`
- **Access:** `student`, `teacher`, `admin`
- **Status:** *Mocked in prototype demo* (Planned for Phase 6 LLM Gateway)

#### Request:
```json
{
  "query_text": "When is my next Machine Learning lab session?",
  "user_context": {
    "role": "student",
    "year": 3,
    "division": "A",
    "batch": "B1"
  }
}
```

#### Response (`200 OK`):
```json
{
  "query_id": "qry_0481",
  "intent": "NEXT_SESSION_LOOKUP",
  "answer": "Your next Machine Learning Lab (CS301-P) is scheduled for today (Wednesday) from 14:00 to 16:00 (Slots TS6 & TS7) in Lab-2 (GPU) with Dr. Priya Sharma.",
  "relevant_sessions": [
    {
      "subject": "Machine Learning Lab",
      "day": "Wednesday",
      "slots": "14:00 – 16:00",
      "room": "Lab-2 (GPU)",
      "teacher": "Dr. Priya Sharma"
    }
  ],
  "disclaimer": "Simulated query answer — AI Gateway under development."
}
```

---

## 8. Timetable Repair & Exception Endpoints

### 8.1 Create Date-Specific Session Exception
- **Endpoint:** `POST /api/v1/timetables/{id}/exceptions`
- **Access:** `admin` only

#### Request:
```json
{
  "session_id": "s_101",
  "exception_date": "2026-11-04",
  "exception_type": "substituted",
  "substitute_teacher_id": "t002",
  "reason": "Faculty medical leave"
}
```

#### Response (`201 Created`):
```json
{
  "exception_id": "exc_5510",
  "session_id": "s_101",
  "date": "2026-11-04",
  "status": "active"
}
```

### 8.2 Trigger Localized Timetable Repair
- **Endpoint:** `POST /api/v1/timetables/{id}/repair`
- **Access:** `admin` only
- **Request:**
  ```json
  {
    "frozen_session_ids": ["s_001", "s_002", "s_003"],
    "unfrozen_session_ids": ["s_101", "s_102"],
    "objective": "MINIMIZE_DISRUPTIONS",
    "reason": "Lab-2 equipment maintenance on Wednesday"
  }
  ```
- **Response (`202 Accepted`):** Queues repair job preserving frozen sessions.
