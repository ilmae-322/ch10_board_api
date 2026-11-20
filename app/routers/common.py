"""라우터에서 함께 쓰는 경로·쿼리 매개변수 타입, 인가 검사, 응답 문서."""

import math
from typing import Annotated

from fastapi import Query

from app.core.exceptions import PermissionDenied
from app.models import User
from app.schemas.common import ErrorResponse

# PostgreSQL INTEGER(id 컬럼)의 최댓값. 이보다 큰 값은 DB에 보내기 전에 422로 거른다.
MAX_DB_ID = 2_147_483_647
# OFFSET이 BIGINT 범위를 넘지 않도록 페이지 번호에 상한을 둔다.
MAX_PAGE = 100_000

Page = Annotated[int, Query(ge=1, le=MAX_PAGE, description="페이지 번호 (1부터 시작)")]
Size = Annotated[int, Query(ge=1, le=50, description="페이지당 항목 수")]

AUTH_ERRORS = {
    401: {"model": ErrorResponse, "description": "인증 실패 (토큰 없음, 만료, 위변조)"},
}


def owner_errors(resource: str) -> dict:
    return {
        **AUTH_ERRORS,
        403: {"model": ErrorResponse, "description": "권한 없음 (작성자가 아님)"},
        404: {"model": ErrorResponse, "description": f"{resource} 없음"},
    }


def total_pages(total: int, size: int) -> int:
    return math.ceil(total / size) if total else 0


def escape_like(keyword: str) -> str:
    """LIKE 검색에서 %, _ 를 와일드카드가 아닌 글자 그대로 찾도록 이스케이프한다."""
    return keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def ensure_owner(author_id: int, user: User, *, allow_admin: bool = False) -> None:
    """인가: 작성자 본인인지 확인한다. allow_admin이면 관리자도 허용한다."""
    if author_id == user.id:
        return
    if allow_admin and user.is_admin:
        return
    raise PermissionDenied("작성자만 수정하거나 삭제할 수 있습니다.")
