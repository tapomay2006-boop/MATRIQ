"""Security utilities for user password hashing and verification using standard library hashlib."""

import hashlib
import hmac
import os


def get_password_hash(password: str) -> str:
    """Hash password using PBKDF2-SHA256 with random salt."""
    salt = os.urandom(16).hex()
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    )
    return f"{salt}:{key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against hashed password."""
    try:
        if ":" not in hashed_password:
            # Fallback for plain text or legacy sha256
            return plain_password == hashed_password

        salt, key_hex = hashed_password.split(":", 1)
        key = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            100_000,
        )
        return hmac.compare_digest(key.hex(), key_hex)
    except Exception:
        return False
