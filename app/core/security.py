"""비밀번호 해싱과 JWT 발급/검증."""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings
from app.core.exceptions import InvalidToken, TokenExpired

settings = get_settings()


def hash_password(password: str) -> str:
    """비밀번호를 bcrypt로 해싱한다. 평문은 어디에도 저장하지 않는다."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(user_id: int, expires_delta: timedelta | None = None) -> str:
    """만료 시간(exp)이 포함된 액세스 토큰을 발급한다."""
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    payload = {"sub": str(user_id), "iat": now, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> int:
    """토큰을 검증하고 사용자 id를 반환한다. 만료와 위변조를 구분해 예외를 던진다."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return int(payload["sub"])
    except jwt.ExpiredSignatureError as error:
        raise TokenExpired(headers={"WWW-Authenticate": "Bearer"}) from error
    except (jwt.InvalidTokenError, KeyError, ValueError) as error:
        raise InvalidToken(headers={"WWW-Authenticate": "Bearer"}) from error
