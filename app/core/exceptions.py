"""커스텀 예외와 전역 예외 핸들러.

모든 오류 응답을 ErrorResponse 한 가지 형태로 통일한다.
    {"code": "POST_NOT_FOUND", "message": "게시글을 찾을 수 없습니다.", "details": null}
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("board")


class AppException(Exception):
    """서비스에서 의도적으로 발생시키는 예외의 부모 클래스."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "BAD_REQUEST"
    message: str = "잘못된 요청입니다."

    def __init__(self, message: str | None = None, *, headers: dict[str, str] | None = None):
        self.message = message or self.message
        self.headers = headers
        super().__init__(self.message)


class InvalidCredentials(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "INVALID_CREDENTIALS"
    message = "이메일 또는 비밀번호가 올바르지 않습니다."


class NotAuthenticated(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "NOT_AUTHENTICATED"
    message = "인증이 필요합니다."


class TokenExpired(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "TOKEN_EXPIRED"
    message = "토큰이 만료되었습니다. 다시 로그인해 주세요."


class InvalidToken(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "INVALID_TOKEN"
    message = "유효하지 않은 토큰입니다."


class PermissionDenied(AppException):
    status_code = status.HTTP_403_FORBIDDEN
    code = "PERMISSION_DENIED"
    message = "이 작업을 수행할 권한이 없습니다."


class PostNotFound(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    code = "POST_NOT_FOUND"
    message = "게시글을 찾을 수 없습니다."


class CommentNotFound(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    code = "COMMENT_NOT_FOUND"
    message = "댓글을 찾을 수 없습니다."


class EmailAlreadyExists(AppException):
    status_code = status.HTTP_409_CONFLICT
    code = "EMAIL_ALREADY_EXISTS"
    message = "이미 가입된 이메일입니다."


class InvalidFile(AppException):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "INVALID_FILE"
    message = "업로드할 수 없는 파일입니다."


class FileTooLarge(AppException):
    status_code = 413
    code = "FILE_TOO_LARGE"
    message = "파일 크기가 허용 범위를 초과했습니다."


def _error_body(code: str, message: str, details: list | None = None) -> dict:
    return {"code": code, "message": message, "details": details}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Pydantic 검증 오류를 "어느 필드가 왜 틀렸는지"만 남긴 형태로 정리한다.
        details = [
            {
                "field": ".".join(str(part) for part in error["loc"] if part != "body"),
                "message": error["msg"].removeprefix("Value error, "),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_error_body("VALIDATION_ERROR", "입력값이 올바르지 않습니다.", details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # 존재하지 않는 경로(404), 허용되지 않은 메서드(405) 등 프레임워크가 만든 오류
        codes = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(codes.get(exc.status_code, "HTTP_ERROR"), str(exc.detail)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # 예상하지 못한 오류: 내부 정보는 로그에만 남기고 응답에는 노출하지 않는다.
        logger.exception("처리되지 않은 예외: %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("INTERNAL_SERVER_ERROR", "서버 내부 오류가 발생했습니다."),
        )
