from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


# NOTE: passlib (1.7.4, unmaintained) crashes with bcrypt >= 4.1/5.x
# ("password cannot be longer than 72 bytes" / missing __about__), which made
# every register/login return HTTP 500. We call bcrypt directly instead.
# Hashes already stored in the database ($2b$...) stay valid.

_BCRYPT_MAX_BYTES = 72


def _to_bytes(password: str) -> bytes:
    # bcrypt only uses the first 72 bytes; truncating matches the behaviour
    # passlib had, so existing hashes keep verifying.
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_to_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    try:
        return bcrypt.checkpw(
            _to_bytes(plain_password),
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        # malformed / non-bcrypt hash -> treat as wrong password, not a 500
        return False


def create_access_token(
    user_id: int,
    role: str,
) -> str:

    expire = (
        datetime.now(timezone.utc)
        + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    )

    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_access_token(token: str) -> dict | None:

    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

    except JWTError:
        return None