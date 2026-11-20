"""라우터에서 공통으로 쓰는 의존성: DB 세션, 현재 로그인한 사용자."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidToken, NotAuthenticated
from app.core.security import decode_access_token
from app.database import get_db
from app.models import User

# auto_error=False: 토큰이 없을 때 FastAPI 기본 오류 대신 우리 에러 형식으로 응답하기 위함
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    db: DbSession,
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> User:
    """Authorization 헤더의 Bearer 토큰을 검증하고 사용자를 반환한다(인증)."""
    if token is None:
        raise NotAuthenticated(headers={"WWW-Authenticate": "Bearer"})

    user_id = decode_access_token(token)
    user = await db.get(User, user_id)
    if user is None:
        # 토큰은 유효하지만 그 사이 회원이 삭제된 경우
        raise InvalidToken(headers={"WWW-Authenticate": "Bearer"})
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
