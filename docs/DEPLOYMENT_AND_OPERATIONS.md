# EduPlus AI Timetable Maker — Deployment & Operations Guide

> **Version:** 0.7.0 (Phase 7)  
> **Scope:** Production configuration, database migrations, container & bare-metal deployment, HTTPS/reverse proxy, backup & restore procedures, and crash recovery.

---

## 1. Environment Configuration

EduPlus validates required production security invariants at startup (`validate_production_config()` in `backend/app/core/config.py`). When `ENVIRONMENT=production`, startup **fails fast** if:
- `SECRET_KEY` is missing, shorter than 32 characters, or equal to the development default.
- `DATABASE_URL` is missing or references a test database.
- `ALLOWED_ORIGINS` contains `*` or `null`.
- `COOKIE_AUTH_ENABLED=true` while `COOKIE_SECURE=false`.
- `ENABLE_DEV_FALLBACKS=true`.

Start from [`.env.production.example`](../.env.production.example) and generate strong secrets:
```bash
openssl rand -hex 32
```
Never commit `.env` or real API keys to Git.

---

## 2. Database Migrations (PostgreSQL 18 + Alembic)

Apply all migrations before starting or upgrading the backend:
```bash
python -m alembic -c backend/alembic.ini upgrade head
```

Verify current migration head (`c4e8a12f9b03` for Phase 7):
```bash
python -m alembic -c backend/alembic.ini current
```

Optional initial baseline seed (development/pilot only — change default passwords immediately):
```bash
python -m backend.app.seed.seed_data
```

---

## 3. Container Deployment (Docker Compose)

1. Copy `.env.production.example` to `.env` and populate `POSTGRES_PASSWORD`, `SECRET_KEY`, and `ALLOWED_ORIGINS`.
2. Build and launch PostgreSQL 18, FastAPI (`api`), and Nginx (`web`):
   ```bash
   docker compose up -d --build
   ```
3. Run Alembic migrations:
   ```bash
   docker compose exec api python -m alembic -c backend/alembic.ini upgrade head
   ```
4. Verify readiness probe:
   ```bash
   curl -fsS http://127.0.0.1/api/v1/health/ready
   ```

### Graceful Shutdown
```bash
docker compose down
```
Data persists in the `eduplus_pgdata` named volume.

---

## 4. Reverse Proxy & HTTPS Guidance

- Serve the static frontend (`index.html`, `admin.html`, `teacher.html`, `student.html`, `src/`) and proxy `/api/` from the **same HTTPS origin** (see [`deploy/nginx.conf`](../deploy/nginx.conf)).
- Serving frontend and API from a single HTTPS origin enables `HttpOnly; Secure; SameSite=Strict` cookie authentication with double-submit `X-CSRF-Token` validation and eliminates cross-origin credential complexity.
- Terminate TLS 1.2+/1.3 at Nginx (or institutional load balancer), redirect HTTP 80 -> HTTPS 443, and enable `Strict-Transport-Security`.

---

## 5. PostgreSQL Backup & Restore Procedures

### Logical Backup (`pg_dump` Custom Format)
```bash
pg_dump -h 127.0.0.1 -p 5433 -U postgres -Fc -f backups/eduplus_$(date +%Y%m%d_%H%M%S).dump eduplus_db
```

### Restore Verification into a Separate Target Database
```bash
createdb -h 127.0.0.1 -p 5433 -U postgres eduplus_restore_verify
pg_restore -h 127.0.0.1 -p 5433 -U postgres -d eduplus_restore_verify --no-owner --clean --if-exists backups/eduplus_YYYYMMDD_HHMMSS.dump
```

Verify row counts after restore:
```sql
SELECT 'departments', COUNT(*) FROM departments
UNION ALL SELECT 'teachers', COUNT(*) FROM teachers
UNION ALL SELECT 'timetable_versions', COUNT(*) FROM timetable_versions
UNION ALL SELECT 'scheduled_sessions', COUNT(*) FROM scheduled_sessions
UNION ALL SELECT 'audit_logs', COUNT(*) FROM audit_logs;
```

Schedule automated daily `pg_dump` backups with offsite encrypted retention and monthly restore drills.

---

## 6. Observability, Health Checks & Recovery

- **Liveness:** `GET /api/v1/health` (returns `200` with service/version/database status).
- **Readiness:** `GET /api/v1/health/ready` (returns `200` when DB query, schema check, and background solver worker pool are healthy; returns `503` if degraded).
- **Request Correlation:** Every response includes `X-Request-ID`, echoed into structured JSON logs (`LOG_FORMAT=json` in production). Secrets, passwords, and Bearer tokens are automatically redacted by `SecretRedactingFilter`.
- **Crash / Interrupted Generation Recovery:** On startup (`lifespan`), `generation_job_manager.recover_orphaned_runs()` transitions any leftover `generation_runs` stuck in `status='running'` to `status='failed'` with diagnostic note `"Interrupted by server restart; safe to retry."`, preventing permanent per-department generation locks.
- **Interrupted Publication Safety:** Version publication (`POST /api/v1/timetable/versions/{id}/publish`) archives previous published versions and publishes the approved version inside a single PostgreSQL transaction, guaranteeing atomic rollback if interrupted.
