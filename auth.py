import os
import hmac
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import config

logger = logging.getLogger(__name__)

# Security scheme for Bearer token extraction
security = HTTPBearer(auto_error=False)

try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    HAS_BCRYPT = False

def hash_password(password: str) -> str:
    """
    Cryptographically secure password hashing.
    Uses bcrypt with cost factor 12 (OWASP recommended standard),
    or falls back to PBKDF2-HMAC-SHA256 with 100,000 iterations and 16-byte random salt.
    """
    if not password:
        raise ValueError("Password cannot be empty")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters")
    if len(password) > 128:
        raise ValueError("Password exceeds maximum allowed length of 128 characters")

    if HAS_BCRYPT:
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
    else:
        salt = os.urandom(16).hex()
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
        return f"$pbkdf2-sha256$100000${salt}${dk.hex()}"

def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verifies a plain password against its bcrypt or PBKDF2 hash using constant-time comparison.
    Guarantees immunity against timing attacks.
    """
    if not password or not hashed_password:
        return False

    try:
        if hashed_password.startswith(("$2b$", "$2a$", "$2y$")):
            if HAS_BCRYPT:
                return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
            return False
        elif hashed_password.startswith("$pbkdf2-sha256$"):
            parts = hashed_password.split("$")
            if len(parts) >= 5:
                iterations = int(parts[2])
                salt = parts[3].encode("utf-8")
                expected_hex = parts[4]
                dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
                return hmac.compare_digest(dk.hex(), expected_hex)
    except Exception as e:
        logger.error(f"Error during password verification: {e}")
        return False
    return False

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Generates a cryptographically signed JWT token following RFC 7519.
    Payload contains user subject, user ID, role, issued-at, and expiration claims.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=config.JWT_EXPIRE_MINUTES)

    to_encode.update({
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp())
    })
    return jwt.encode(to_encode, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decodes and validates a JWT token signature and expiration.
    Returns the decoded claims dictionary if valid, or None if invalid/expired.
    """
    try:
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.info("Access token has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid access token: {e}")
        return None

async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[Dict[str, Any]]:
    """
    Non-blocking optional auth dependency.
    Returns user claims if valid Bearer token provided, otherwise None.
    Preserves backwards compatibility for endpoints accessible both anonymously and authenticated.
    """
    if not credentials or not credentials.credentials:
        return None
    return decode_access_token(credentials.credentials)

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Dict[str, Any]:
    """
    Strict auth dependency.
    Raises HTTP 401 Unauthorized if Bearer token is missing, invalid, or expired.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return payload
