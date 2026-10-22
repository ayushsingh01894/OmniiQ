"""Password hashing and access tokens."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()
# Verified against when the email is unknown, so login timing doesn't reveal which emails exist.
_DUMMY_HASH = _hasher.hash("not-a-real-password")

_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def burn_password_check(password: str) -> None:
    verify_password(password, _DUMMY_HASH)


def create_access_token(
    user_id: uuid.UUID, secret_key: str, expires_minutes: int, now: datetime | None = None
) -> str:
    issued = now or datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "iat": issued,
        "exp": issued + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(claims, secret_key, algorithm=_ALGORITHM)


def decode_access_token(token: str, secret_key: str) -> uuid.UUID | None:
    """Returns the user id, or None for any invalid, tampered or expired token."""
    try:
        claims = jwt.decode(
            token, secret_key, algorithms=[_ALGORITHM], options={"require": ["exp", "sub"]}
        )
        return uuid.UUID(str(claims["sub"]))
    except (jwt.PyJWTError, ValueError):
        return None
