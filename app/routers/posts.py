import math
import uuid
from pathlib import Path as FilePath
from typing import Annotated

import aiofiles
import aiofiles.os
from fastapi import APIRouter, File, Path, Query, Response, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.cache import TTLCache
from app.core.config import get_settings
from app.core.exceptions import FileTooLarge, InvalidFile, PermissionDenied, PostNotFound
from app.deps import CurrentUser, DbSession
from app.models import Post, User
from app.schemas.common import ErrorResponse
from app.schemas.post import PostCreate, PostListResponse, PostResponse, PostUpdate

router = APIRouter(prefix="/posts", tags=["게시글"])
settings = get_settings()

# 게시글 목록 응답 캐시. 글이 바뀌면(작성/수정/삭제/이미지 변경) 전체를 비운다.
post_list_cache = TTLCache(settings.cache_ttl_seconds)

PostId = Annotated[int, Path(ge=1, description="게시글 id", examples=[1])]

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}

AUTH_ERRORS = {
    401: {"model": ErrorResponse, "description": "인증 실패 (토큰 없음, 만료, 위변조)"},
}
OWNER_ERRORS = {
    **AUTH_ERRORS,
    403: {"model": ErrorResponse, "description": "권한 없음 (작성자가 아님)"},
    404: {"model": ErrorResponse, "description": "게시글 없음"},
}


async def get_post_or_404(db: AsyncSession, post_id: int) -> Post:
    """게시글을 작성자와 함께 한 번의 쿼리(JOIN)로 조회한다."""
    post = await db.scalar(
        select(Post).options(joinedload(Post.author)).where(Post.id == post_id)
    )
    if post is None:
        raise PostNotFound()
    return post


def ensure_author(post: Post, user: User, *, allow_admin: bool = False) -> None:
    """인가: 작성자 본인인지 확인한다. allow_admin이면 관리자도 허용한다."""
    if post.author_id == user.id:
        return
    if allow_admin and user.is_admin:
        return
    raise PermissionDenied("작성자만 수정하거나 삭제할 수 있습니다.")


@router.get(
    "",
    response_model=PostListResponse,
    summary="게시글 목록 조회",
    responses={422: {"model": ErrorResponse, "description": "쿼리 매개변수 검증 실패"}},
)
async def list_posts(
    response: Response,
    db: DbSession,
    page: Annotated[int, Query(ge=1, description="페이지 번호 (1부터 시작)")] = 1,
    size: Annotated[int, Query(ge=1, le=50, description="페이지당 게시글 수")] = 10,
    keyword: Annotated[
        str | None, Query(max_length=50, description="제목 또는 내용 검색어")
    ] = None,
) -> PostListResponse:
    """최신순으로 게시글 목록을 반환한다. 누구나 조회할 수 있다.

    - 같은 조건의 요청은 짧은 시간 동안 캐시된 결과를 반환한다.
      응답 헤더 `X-Cache`로 `HIT`/`MISS`를 확인할 수 있다.
    - 작성자 정보는 JOIN으로 함께 조회해 N+1 쿼리를 방지한다.
    """
    keyword = keyword.strip() if keyword else None
    cache_key = f"posts:{page}:{size}:{keyword or ''}"

    cached = post_list_cache.get(cache_key)
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        return cached

    conditions = []
    if keyword:
        pattern = f"%{keyword}%"
        conditions.append(or_(Post.title.ilike(pattern), Post.content.ilike(pattern)))

    total = await db.scalar(select(func.count()).select_from(Post).where(*conditions)) or 0

    result = await db.scalars(
        select(Post)
        .options(joinedload(Post.author))
        .where(*conditions)
        .order_by(Post.created_at.desc(), Post.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    )

    payload = PostListResponse(
        items=[PostResponse.model_validate(post) for post in result.all()],
        total=total,
        page=page,
        size=size,
        total_pages=math.ceil(total / size) if total else 0,
    )
    post_list_cache.set(cache_key, payload)
    response.headers["X-Cache"] = "MISS"
    return payload


@router.get(
    "/{post_id}",
    response_model=PostResponse,
    summary="게시글 단건 조회",
    responses={404: {"model": ErrorResponse, "description": "게시글 없음"}},
)
async def read_post(post_id: PostId, db: DbSession) -> Post:
    """게시글 하나를 반환한다. 누구나 조회할 수 있다."""
    return await get_post_or_404(db, post_id)


@router.post(
    "",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
    summary="게시글 작성",
    responses={
        **AUTH_ERRORS,
        422: {"model": ErrorResponse, "description": "입력값 검증 실패"},
    },
)
async def create_post(payload: PostCreate, db: DbSession, current_user: CurrentUser) -> Post:
    """로그인한 회원이 게시글을 작성한다. 작성자는 토큰의 사용자로 자동 지정된다."""
    post = Post(title=payload.title, content=payload.content, author=current_user)
    db.add(post)
    await db.commit()
    await db.refresh(post)

    post_list_cache.clear()
    return post


@router.patch(
    "/{post_id}",
    response_model=PostResponse,
    summary="게시글 수정",
    responses={
        **OWNER_ERRORS,
        422: {"model": ErrorResponse, "description": "입력값 검증 실패"},
    },
)
async def update_post(
    post_id: PostId,
    payload: PostUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> Post:
    """작성자 본인만 수정할 수 있다. 보낸 항목만 변경한다."""
    post = await get_post_or_404(db, post_id)
    ensure_author(post, current_user)

    for field, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(post, field, value)

    await db.commit()
    await db.refresh(post)

    post_list_cache.clear()
    return post


@router.delete(
    "/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="게시글 삭제",
    responses=OWNER_ERRORS,
)
async def delete_post(post_id: PostId, db: DbSession, current_user: CurrentUser) -> None:
    """작성자 본인 또는 관리자만 삭제할 수 있다."""
    post = await get_post_or_404(db, post_id)
    ensure_author(post, current_user, allow_admin=True)

    image_url = post.image_url
    await db.delete(post)
    await db.commit()

    await _remove_image_file(image_url)
    post_list_cache.clear()


@router.post(
    "/{post_id}/image",
    response_model=PostResponse,
    summary="게시글 이미지 업로드",
    responses={
        **OWNER_ERRORS,
        400: {"model": ErrorResponse, "description": "허용되지 않은 파일 형식"},
        413: {"model": ErrorResponse, "description": "파일 크기 초과"},
    },
)
async def upload_post_image(
    post_id: PostId,
    db: DbSession,
    current_user: CurrentUser,
    file: Annotated[UploadFile, File(description="이미지 파일 (JPEG, PNG, GIF, WebP / 최대 5MB)")],
) -> Post:
    """작성자 본인만 게시글에 이미지를 첨부할 수 있다. 기존 이미지는 교체된다.

    업로드한 파일은 응답의 `image_url` 경로로 내려받을 수 있다.
    """
    post = await get_post_or_404(db, post_id)
    ensure_author(post, current_user)

    extension = ALLOWED_IMAGE_TYPES.get(file.content_type or "")
    if extension is None:
        raise InvalidFile("이미지 파일(JPEG, PNG, GIF, WebP)만 업로드할 수 있습니다.")

    # 사용자가 보낸 파일명은 쓰지 않고 서버가 만든 이름으로 저장한다(경로 조작 방지).
    filename = f"{uuid.uuid4().hex}{extension}"
    destination = FilePath(settings.upload_dir) / filename

    # 파일을 조금씩 읽어 비동기로 저장하면서 크기 제한을 확인한다.
    written = 0
    try:
        async with aiofiles.open(destination, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > settings.max_upload_bytes:
                    raise FileTooLarge(
                        f"파일은 {settings.max_upload_bytes // (1024 * 1024)}MB 이하만 업로드할 수 있습니다."
                    )
                await out.write(chunk)
    except FileTooLarge:
        await _remove_file(destination)
        raise

    if written == 0:
        await _remove_file(destination)
        raise InvalidFile("빈 파일은 업로드할 수 없습니다.")

    old_image_url = post.image_url
    post.image_url = f"/uploads/{filename}"
    await db.commit()
    await db.refresh(post)

    await _remove_image_file(old_image_url)
    post_list_cache.clear()
    return post


async def _remove_file(path: FilePath) -> None:
    try:
        await aiofiles.os.remove(path)
    except FileNotFoundError:
        pass


async def _remove_image_file(image_url: str | None) -> None:
    """image_url(/uploads/파일명)에 해당하는 실제 파일을 지운다."""
    if image_url:
        await _remove_file(FilePath(settings.upload_dir) / FilePath(image_url).name)
