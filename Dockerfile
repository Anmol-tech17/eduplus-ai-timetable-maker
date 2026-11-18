# EduPlus AI Timetable Maker — Production Backend Container
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install minimal system dependencies for psycopg2 / healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/backend/requirements.txt

# Copy backend source & migrations
COPY backend /app/backend

# Create non-root application user
RUN groupadd -r eduplus && useradd -r -g eduplus eduplus \
    && chown -R eduplus:eduplus /app
USER eduplus

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/v1/health/ready || exit 1

# Run with multiple workers (token revocation & rate limiting are PostgreSQL-backed)
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
