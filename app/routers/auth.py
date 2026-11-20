from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.exceptions import EmailAlreadyExists, InvalidCredentials
from app.core.security import create_access_token, hash_password, verify_password
from app.deps import CurrentUser, DbSession
from app.models import User
from app.schemas.common import ErrorResponse
from app.schemas.user import Token, UserCreate, UserResponse

router = APIRouter(prefix="/auth", tags=["인증"])
settings = get_settings()


@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="회원가입",
    responses={
        409: {"model": ErrorResponse, "description": "이미 가입된 이메일"},
        422: {"model": ErrorResponse, "description": "입력값 검증 실패"},
    },
)
async def signup(payload: UserCreate, db: DbSession) -> User:
    """이메일, 비밀번호, 닉네임으로 가입한다. 비밀번호는 bcrypt 해시로 저장한다."""
    email = payload.email.lower()

    existing = await db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise EmailAlreadyExists()

    user = User(
        email=email,
        hashed_password=hash_password(payload.password),
        nickname=payload.nickname,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as error:
        # 동시에 같은 이메일로 가입한 경우 UNIQUE 제약이 최종적으로 막는다.
        await db.rollback()
        raise EmailAlreadyExists() from error

    await db.refresh(user)
    return user


@router.post(
    "/login",
    response_model=Token,
    summary="로그인 (JWT 발급)",
    responses={401: {"model": ErrorResponse, "description": "이메일 또는 비밀번호 불일치"}},
)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
) -> Token:
    """로그인에 성공하면 액세스 토큰을 발급한다.

    Swagger UI의 **Authorize** 버튼과 연동하기 위해 OAuth2 표준 폼 형식을 사용한다.
    `username` 칸에 **이메일**을 입력한다.
    """
    user = await db.scalar(select(User).where(User.email == form.username.lower()))

    # 계정 존재 여부를 노출하지 않도록 이메일 오류와 비밀번호 오류를 같은 메시지로 응답한다.
    if user is None or not verify_password(form.password, user.hashed_password):
        raise InvalidCredentials(headers={"WWW-Authenticate": "Bearer"})

    return Token(
        access_token=create_access_token(user.id),
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="내 정보 조회",
    responses={401: {"model": ErrorResponse, "description": "인증 실패 (토큰 없음, 만료, 위변조)"}},
)
async def read_me(current_user: CurrentUser) -> User:
    """토큰의 주인(현재 로그인한 회원) 정보를 반환한다."""
    return current_user
