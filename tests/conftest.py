"""테스트 공통 설정.

테스트는 운영 DB가 아닌 별도 PostgreSQL(test-db)을 사용한다.
    docker compose --profile test up -d test-db
    uv run pytest
다른 DB를 쓰려면 TEST_DATABASE_URL 환경 변수로 지정한다.
"""

import os
import tempfile

# 앱 모듈을 가져오기 전에 설정을 바꿔야 한다(설정은 처음 import될 때 한 번 읽힌다).
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://board:board-password@localhost:5433/board_test",
)
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-pytest-only-0123456789"
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="board-test-uploads-")

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import text, update  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.routers.posts import post_list_cache  # noqa: E402

PASSWORD = "password1234"


@pytest.fixture(scope="session", autouse=True)
async def create_tables():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
async def clean_database():
    """테스트마다 모든 테이블을 비우고 id를 1부터 다시 시작한다."""
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    post_list_cache.clear()
    yield


@pytest.fixture
async def client():
    # raise_app_exceptions=False: 500 오류도 예외 대신 응답으로 받아 상태 코드를 검사한다.
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def signup(client: httpx.AsyncClient, email: str, nickname: str = "테스터") -> dict:
    response = await client.post(
        "/auth/signup", json={"email": email, "password": PASSWORD, "nickname": nickname}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def login(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    response = await client.post("/auth/login", data={"username": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def make_admin(email: str) -> None:
    async with SessionLocal() as session:
        await session.execute(update(User).where(User.email == email).values(role="admin"))
        await session.commit()


@pytest.fixture
async def alice(client) -> dict[str, str]:
    """게시글 작성자 역할의 회원 인증 헤더."""
    await signup(client, "alice@example.com", "앨리스")
    return await login(client, "alice@example.com")


@pytest.fixture
async def bob(client) -> dict[str, str]:
    """작성자가 아닌 다른 회원의 인증 헤더."""
    await signup(client, "bob@example.com", "바비")
    return await login(client, "bob@example.com")


@pytest.fixture
async def admin(client) -> dict[str, str]:
    await signup(client, "admin@example.com", "관리자")
    await make_admin("admin@example.com")
    return await login(client, "admin@example.com")


@pytest.fixture
async def post(client, alice) -> dict:
    """alice가 작성한 게시글."""
    response = await client.post(
        "/posts", headers=alice, json={"title": "첫 번째 글", "content": "안녕하세요"}
    )
    assert response.status_code == 201, response.text
    return response.json()
