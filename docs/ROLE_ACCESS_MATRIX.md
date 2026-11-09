# EduPlus — Role Access Matrix

> **Document ID:** ROLE_ACCESS_MATRIX  
> **Version:** 0.1

---

## Demo vs Production

> ⚠️ **The prototype demo uses frontend-only role routing.** In production, every permission must be enforced on the server. This matrix defines the intended production behavior.

---

## 1. Academic Data

| Resource | Admin | Teacher | Student |
|---------|-------|---------|---------|
| View departments, years, divisions | ✅ | ✅ | ✅ |
| Create / edit academic structure | ✅ | ❌ | ❌ |
| View subjects | ✅ | ✅ | ✅ |
| Create / edit subjects | ✅ | ❌ | ❌ |
| View enrollment groups | ✅ | ✅ (own) | ❌ |
| Create / edit enrollment groups | ✅ | ❌ | ❌ |
| View teaching assignments | ✅ | ✅ (own) | ❌ |
| Create / edit teaching assignments | ✅ | ❌ | ❌ |

---

## 2. Teachers and Rooms

| Resource | Admin | Teacher | Student |
|---------|-------|---------|---------|
| View teacher list | ✅ | ✅ | ❌ |
| Edit teacher profile | ✅ | ✅ (own only) | ❌ |
| Configure teacher availability | ✅ | ✅ (own only) | ❌ |
| View room list | ✅ | ✅ | ❌ |
| Create / edit rooms | ✅ | ❌ | ❌ |
| Configure room unavailability | ✅ | ❌ | ❌ |

---

## 3. Timetable Generation

| Action | Admin | Teacher | Student |
|--------|-------|---------|---------|
| Trigger timetable generation | ✅ | ❌ | ❌ |
| View generation job status | ✅ | ❌ | ❌ |
| View solver status and diagnostics | ✅ | ❌ | ❌ |
| View candidate timetables (unpublished) | ✅ | ❌ | ❌ |
| Compare candidates | ✅ | ❌ | ❌ |
| View validation results | ✅ | ❌ | ❌ |
| View conflict explanations | ✅ | ❌ | ❌ |

---

## 4. Timetable Publication and Versioning

| Action | Admin | Teacher | Student |
|--------|-------|---------|---------|
| Publish a validated timetable | ✅ | ❌ | ❌ |
| View published timetable (own group) | ✅ | ✅ | ✅ |
| View published timetable (all groups) | ✅ | ❌ | ❌ |
| View unpublished draft timetables | ✅ | ❌ | ❌ |
| View timetable version history | ✅ | ❌ | ❌ |
| Rollback to a previous version | ✅ | ❌ | ❌ |
| Archive a timetable version | ✅ | ❌ | ❌ |

---

## 5. Repair Operations

| Action | Admin | Teacher | Student |
|--------|-------|---------|---------|
| Trigger a repair run | ✅ | ❌ | ❌ |
| View repair run results | ✅ | ❌ | ❌ |
| Approve repair and publish result | ✅ | ❌ | ❌ |
| Submit a request that may trigger repair | ❌ | ✅ | ❌ |
| View own repair-triggered session changes | ❌ | ✅ | ✅ (own sessions) |

---

## 6. Session Exceptions

| Action | Admin | Teacher | Student |
|--------|-------|---------|---------|
| Create cancellation exception | ✅ | Propose only | ❌ |
| Create substitution exception | ✅ | Propose only | ❌ |
| Create room change exception | ✅ | ❌ | ❌ |
| View exceptions for own sessions | ✅ | ✅ | ✅ |
| View all exceptions | ✅ | ❌ | ❌ |

---

## 7. Policy and Scheduling Configuration

| Action | Admin | Teacher | Student |
|--------|-------|---------|---------|
| View scheduling rules (read-only summary) | ✅ | ✅ | ❌ |
| Edit Level B rule parameters | ✅ | ❌ | ❌ |
| Approve Level B policy relaxation | ✅ | ❌ | ❌ |
| Override Level A constraint | ❌ (blocked) | ❌ | ❌ |
| Configure lunch policy | ✅ | ❌ | ❌ |
| Configure working days | ✅ | ❌ | ❌ |

---

## 8. Requests and Queries

| Action | Admin | Teacher | Student |
|--------|-------|---------|---------|
| Submit reschedule request | ❌ | ✅ | ❌ |
| Submit substitution request | ❌ | ✅ | ❌ |
| Submit cancellation request | ❌ | ✅ | ❌ |
| View own requests | ❌ | ✅ | ❌ |
| View all incoming requests | ✅ | ❌ | ❌ |
| Approve / reject requests | ✅ | ❌ | ❌ |
| Submit student query | ❌ | ❌ | ✅ |
| Submit teacher query | ❌ | ✅ | ❌ |
| View own query status | ❌ | ✅ | ✅ |
| View all queries | ✅ | ❌ | ❌ |
| Respond to queries (admin) | ✅ | ❌ | ❌ |

---

## 9. Audit Log

| Action | Admin | Teacher | Student |
|--------|-------|---------|---------|
| View audit log entries | ✅ (own department) | ❌ | ❌ |
| Create audit log entries | System only | — | — |
| Delete audit log entries | ❌ (immutable) | ❌ | ❌ |

---

## 10. User Management

| Action | Admin | Teacher | Student |
|--------|-------|---------|---------|
| Create user accounts | ✅ (dept scope) | ❌ | ❌ |
| Deactivate accounts | ✅ (dept scope) | ❌ | ❌ |
| Change own password | ✅ | ✅ | ✅ |
| Reset another user's password | ✅ (dept scope) | ❌ | ❌ |
| View user list | ✅ (dept scope) | ❌ | ❌ |

---

## Demo Behavior vs Production Authorization

| Behavior | Demo | Production |
|---------|------|-----------|
| Route guard | Frontend-only (JS redirect) | Server-side RBAC on every endpoint |
| Auth token | `sessionStorage` mock | JWT / server session |
| Admin scope | Entire department | Enforced per department FK |
| Student data access | No restriction (prototype) | Division + batch + enrollment group filtered |
| Unpublished timetable | Visible in admin panel | Hidden from teacher + student API |
