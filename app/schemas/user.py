import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    """회원가입 요청."""

    email: EmailStr = Field(examples=["user@example.com"])
    password: str = Field(min_length=8, max_length=64, examples=["password1234"])
    nickname: str = Field(min_length=2, max_length=30, examples=["홍길동"])

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
            raise ValueError("비밀번호는 영문과 숫자를 모두 포함해야 합니다.")
        if " " in value:
            raise ValueError("비밀번호에는 공백을 사용할 수 없습니다.")
        return value

    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("닉네임은 공백을 제외하고 2자 이상이어야 합니다.")
        return value


class UserResponse(BaseModel):
    """회원 응답. 비밀번호 해시는 포함하지 않는다."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    nickname: str
    role: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="토큰 만료까지 남은 시간(초)")
