"""비밀번호 해싱과 JWT 발급/검증."""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings
from app.core.exceptions import InvalidToken, TokenExpired

settings = get_settings()

# bcrypt는 72바이트까지만 처리한다(bcrypt 5.0부터는 초과 시 ValueError).
BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    """비밀번호를 bcrypt로 해싱한다. 평문은 어디에도 저장하지 않는다."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# 없는 계정으로 로그인할 때도 같은 시간만큼 해시를 비교하기 위한 값(응답 시간으로 계정 존재 여부 노출 방지)
DUMMY_PASSWORD_HASH = hash_password("dummy-password-0")


def verify_password(password: str, hashed_password: str | None) -> bool:
    encoded = password.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_BYTES:
        # 가입 시 72바이트 초과 비밀번호는 거부하므로 일치할 수 없다.
        bcrypt.checkpw(b"", DUMMY_PASSWORD_HASH.encode("utf-8"))
        return False
    target = hashed_password or DUMMY_PASSWORD_HASH
    matched = bcrypt.checkpw(encoded, target.encode("utf-8"))
    return matched and hashed_password is not None


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
