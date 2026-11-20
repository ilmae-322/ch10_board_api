from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.post import AuthorSummary


def _strip_content(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("댓글에는 공백이 아닌 내용을 입력해야 합니다.")
    return value


class CommentCreate(BaseModel):
    """댓글 작성 요청."""

    content: str = Field(min_length=1, max_length=1000, examples=["좋은 글 감사합니다."])

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        return _strip_content(value)


class CommentUpdate(CommentCreate):
    """댓글 수정 요청. 댓글은 내용 하나뿐이라 작성 요청과 형식이 같다."""


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: int
    content: str
    author: AuthorSummary
    created_at: datetime
    updated_at: datetime


class CommentListResponse(BaseModel):
    """페이지네이션이 적용된 댓글 목록(작성 순)."""

    items: list[CommentResponse]
    total: int
    page: int
    size: int
    total_pages: int
