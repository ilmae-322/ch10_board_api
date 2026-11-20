from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    field: str = Field(examples=["password"])
    message: str = Field(examples=["비밀번호는 영문과 숫자를 모두 포함해야 합니다."])


class ErrorResponse(BaseModel):
    """모든 오류 응답이 공통으로 따르는 형식."""

    code: str = Field(examples=["POST_NOT_FOUND"])
    message: str = Field(examples=["게시글을 찾을 수 없습니다."])
    details: list[ErrorDetail] | None = Field(default=None, description="입력값 검증 오류일 때 필드별 상세 내용")
