from typing import Annotated

from fastapi import APIRouter, Path, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import CommentNotFound
from app.deps import CurrentUser, DbSession
from app.models import Comment
from app.routers.common import AUTH_ERRORS, MAX_DB_ID, Page, Size, ensure_owner, owner_errors, total_pages
from app.routers.posts import POST_NOT_FOUND, PostId, ensure_post_exists, post_list_cache
from app.schemas.common import ErrorResponse
from app.schemas.comment import CommentCreate, CommentListResponse, CommentResponse, CommentUpdate

router = APIRouter(tags=["댓글"])

CommentId = Annotated[int, Path(ge=1, le=MAX_DB_ID, description="댓글 id", examples=[1])]

COMMENT_OWNER_ERRORS = owner_errors("댓글")
VALIDATION_ERROR = {422: {"model": ErrorResponse, "description": "입력값 검증 실패"}}


async def get_comment_or_404(db: AsyncSession, comment_id: int) -> Comment:
    comment = await db.scalar(
        select(Comment).options(joinedload(Comment.author)).where(Comment.id == comment_id)
    )
    if comment is None:
        raise CommentNotFound()
    return comment


@router.get(
    "/posts/{post_id}/comments",
    response_model=CommentListResponse,
    summary="댓글 목록 조회",
    responses={**POST_NOT_FOUND, **VALIDATION_ERROR},
)
async def list_comments(
    post_id: PostId,
    db: DbSession,
    page: Page = 1,
    size: Size = 20,
) -> CommentListResponse:
    """게시글의 댓글을 작성 순(오래된 순)으로 반환한다. 누구나 조회할 수 있다."""
    await ensure_post_exists(db, post_id)

    total = await db.scalar(
        select(func.count()).select_from(Comment).where(Comment.post_id == post_id)
    ) or 0
    result = await db.scalars(
        select(Comment)
        .options(joinedload(Comment.author))
        .where(Comment.post_id == post_id)
        .order_by(Comment.created_at, Comment.id)
        .offset((page - 1) * size)
        .limit(size)
    )
    return CommentListResponse(
        items=[CommentResponse.model_validate(comment) for comment in result.all()],
        total=total,
        page=page,
        size=size,
        total_pages=total_pages(total, size),
    )


@router.post(
    "/posts/{post_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="댓글 작성",
    responses={**AUTH_ERRORS, **POST_NOT_FOUND, **VALIDATION_ERROR},
)
async def create_comment(
    post_id: PostId,
    payload: CommentCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> Comment:
    """로그인한 회원이 게시글에 댓글을 단다."""
    await ensure_post_exists(db, post_id)

    comment = Comment(content=payload.content, post_id=post_id, author=current_user)
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    post_list_cache.clear()  # 목록의 댓글 수가 바뀐다.
    return comment


@router.patch(
    "/comments/{comment_id}",
    response_model=CommentResponse,
    summary="댓글 수정",
    responses={**COMMENT_OWNER_ERRORS, **VALIDATION_ERROR},
)
async def update_comment(
    comment_id: CommentId,
    payload: CommentUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> Comment:
    """작성자 본인만 수정할 수 있다."""
    comment = await get_comment_or_404(db, comment_id)
    ensure_owner(comment.author_id, current_user)

    comment.content = payload.content
    await db.commit()
    await db.refresh(comment)
    return comment


@router.delete(
    "/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="댓글 삭제",
    responses=COMMENT_OWNER_ERRORS,
)
async def delete_comment(comment_id: CommentId, db: DbSession, current_user: CurrentUser) -> None:
    """작성자 본인 또는 관리자만 삭제할 수 있다."""
    comment = await get_comment_or_404(db, comment_id)
    ensure_owner(comment.author_id, current_user, allow_admin=True)

    await db.delete(comment)
    await db.commit()
    post_list_cache.clear()
