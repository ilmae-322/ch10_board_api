from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _strip_and_require(value: str, label: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{label}에는 공백이 아닌 내용을 입력해야 합니다.")
    return value


class PostCreate(BaseModel):
    """게시글 작성 요청."""

    title: str = Field(min_length=1, max_length=100, examples=["첫 번째 글"])
    content: str = Field(min_length=1, max_length=5000, examples=["안녕하세요, 게시판 API 테스트입니다."])

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _strip_and_require(value, "제목")

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        return _strip_and_require(value, "내용")


class PostUpdate(BaseModel):
    """게시글 수정 요청. 바꿀 항목만 보낸다(PATCH)."""

    title: str | None = Field(default=None, min_length=1, max_length=100, examples=["수정한 제목"])
    content: str | None = Field(default=None, min_length=1, max_length=5000, examples=["수정한 내용"])

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        return None if value is None else _strip_and_require(value, "제목")

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str | None) -> str | None:
        return None if value is None else _strip_and_require(value, "내용")

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "PostUpdate":
        if self.title is None and self.content is None:
            raise ValueError("수정할 항목(title, content)을 하나 이상 입력해야 합니다.")
        return self


class AuthorSummary(BaseModel):
    """게시글에 함께 내려가는 작성자 정보. 이메일 등 개인 정보는 제외한다."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nickname: str


class PostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    image_url: str | None
    author: AuthorSummary
    like_count: int = Field(description="좋아요 수")
    comment_count: int = Field(description="댓글 수")
    created_at: datetime
    updated_at: datetime


class LikeResponse(BaseModel):
    """좋아요 누르기/취소 결과."""

    post_id: int
    liked: bool = Field(description="요청 후 현재 사용자가 좋아요한 상태인지")
    like_count: int


class PostListResponse(BaseModel):
    """페이지네이션이 적용된 게시글 목록."""

    items: list[PostResponse]
    total: int = Field(description="조건에 맞는 전체 게시글 수")
    page: int
    size: int
    total_pages: int
