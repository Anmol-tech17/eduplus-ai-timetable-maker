"""
backend/app/core/security.py
EduPlus AI Timetable Maker — Security & Hashing Utilities
"""

from passlib.hash import pbkdf2_sha256


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against the stored hash using PBKDF2-SHA256."""
    try:
        return pbkdf2_sha256.verify(plain_password, hashed_password)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Generates a secure password hash using PBKDF2-SHA256."""
    return pbkdf2_sha256.hash(password)
