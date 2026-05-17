from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
from typing import Any

from jose import JWTError, jwt

from app.core.config import settings


PASSWORD_ITERATIONS = 260_000


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        algorithm, iterations, salt, stored_hash = hashed_password.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            bytes.fromhex(salt),
            int(iterations),
        ).hex()
        return hmac.compare_digest(candidate, stored_hash)
    except ValueError:
        return False


def get_password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest}"


def create_access_token(subject: str, role: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload: dict[str, Any] = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError as exc:
        raise ValueError("Invalid or expired authentication token") from exc
