"""JWT token creation/verification and password hashing utilities."""

import os
import warnings
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))

if not JWT_SECRET:
    warnings.warn(
        "JWT_SECRET is not set — JWT auth will be insecure. "
        "Set JWT_SECRET in your .env file.",
        stacklevel=2,
    )


def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Check a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token(user_id: int, username: str) -> str:
    """Create a JWT with user_id and username in the payload."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and verify a JWT. Raises jwt.InvalidTokenError on failure."""
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    payload["sub"] = int(payload["sub"])
    return payload
