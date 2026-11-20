import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import models  # noqa: F401  (테이블 생성을 위해 모델을 등록한다)
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.middleware import log_requests
from app.database import Base, engine
from app.routers import auth, comments, posts

settings = get_settings()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버 시작 시: 테이블이 없으면 생성한다.
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield
    # 서버 종료 시: DB 연결 풀을 정리한다.
    await engine.dispose()


DESCRIPTION = """
JWT 인증·인가가 적용된 RESTful 게시판 API입니다.

### 테스트 순서
1. **POST /auth/signup** 으로 회원가입
2. 오른쪽 위 **Authorize** 버튼을 눌러 `username`에 이메일, `password`에 비밀번호 입력
3. **POST /posts** 로 게시글 작성, **PATCH / DELETE** 로 수정·삭제 (작성자 본인만 가능)
4. **POST /posts/{post_id}/comments** 로 댓글, **PUT /posts/{post_id}/like** 로 좋아요

### 공통 오류 형식
모든 오류는 `{"code": "...", "message": "...", "details": [...]}` 형식으로 응답합니다.
"""

app = FastAPI(
    title="게시판 API",
    description=DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "인증", "description": "회원가입, 로그인(JWT 발급), 내 정보"},
        {"name": "게시글", "description": "게시글 CRUD, 이미지 업로드, 좋아요"},
        {"name": "댓글", "description": "댓글 작성·조회·수정·삭제"},
        {"name": "상태", "description": "서버 상태 확인"},
    ],
)

# 미들웨어: CORS(외부 클라이언트 연동), 요청 로깅 + 처리 시간 측정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Process-Time", "X-Cache"],
)
app.middleware("http")(log_requests)

register_exception_handlers(app)

app.include_router(auth.router)
app.include_router(posts.router)
app.include_router(comments.router)

# 업로드한 이미지를 /uploads/파일명 경로로 제공한다.
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


@app.get("/health", tags=["상태"], summary="서버 상태 확인")
async def health() -> dict[str, str]:
    return {"status": "ok"}
