"""
backend/app/services/audit.py
EduPlus AI Timetable Maker — Security & Operational Audit Logging Service

Records actor, action, target entity, sanitized payload, IP address, and timestamp.
Strictly strips sensitive fields (passwords, tokens, API keys, secrets) before persisting.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional
from fastapi import Request
from sqlalchemy.orm import Session

from backend.app.core.logging import logger
from backend.app.models.security import AuditLog

_SENSITIVE_KEY_FRAGMENTS = (
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "hash",
)


def _sanitize_value(val: Any) -> Any:
    if isinstance(val, dict):
        sanitized: Dict[str, Any] = {}
        for k, v in val.items():
            key_lower = str(k).lower()
            if any(frag in key_lower for frag in _SENSITIVE_KEY_FRAGMENTS):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = _sanitize_value(v)
        return sanitized
    if isinstance(val, list):
        return [_sanitize_value(item) for item in val]
    if isinstance(val, uuid.UUID):
        return str(val)
    return val


def extract_client_ip(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    if request.client and request.client.host:
        return str(request.client.host)[:45]
    return None


def record_audit_event(
    db: Session,
    action: str,
    entity_type: str,
    user_id: Optional[uuid.UUID] = None,
    entity_id: Optional[uuid.UUID] = None,
    payload: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None,
    ip_address: Optional[str] = None,
    commit: bool = False,
) -> AuditLog:
    """
    Create an immutable AuditLog entry.
    Sensitive fields in payload are automatically redacted.
    """
    safe_payload = _sanitize_value(payload) if payload is not None else None
    client_ip = ip_address or extract_client_ip(request)

    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=safe_payload,
        ip_address=client_ip,
    )
    db.add(entry)
    if commit:
        try:
            db.commit()
            db.refresh(entry)
        except Exception as exc:
            db.rollback()
            logger.error(f"Failed to commit audit log ({action}): {exc}")
    else:
        db.flush()
    return entry
