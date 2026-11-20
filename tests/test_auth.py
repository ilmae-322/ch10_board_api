from datetime import timedelta

from app.core.security import create_access_token

from tests.conftest import PASSWORD, login, signup


async def test_signup_returns_user_without_password(client):
    response = await client.post(
        "/auth/signup",
        json={"email": "User@Example.com", "password": PASSWORD, "nickname": "  홍길동  "},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "user@example.com"  # 소문자로 정규화
    assert body["nickname"] == "홍길동"  # 앞뒤 공백 제거
    assert body["role"] == "user"
    assert "password" not in body and "hashed_password" not in body


async def test_signup_duplicate_email_is_409_case_insensitive(client):
    await signup(client, "dup@example.com")

    response = await client.post(
        "/auth/signup", json={"email": "DUP@example.com", "password": PASSWORD, "nickname": "중복"}
    )

    assert response.status_code == 409
    assert response.json()["code"] == "EMAIL_ALREADY_EXISTS"


async def test_signup_weak_password_returns_field_details(client):
    response = await client.post(
        "/auth/signup", json={"email": "a@example.com", "password": "onlyletters", "nickname": "약함"}
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["details"][0]["field"] == "password"
    assert "영문과 숫자" in body["details"][0]["message"]


async def test_signup_password_over_72_bytes_is_422_not_500(client):
    # 한글 30자(90바이트) + 영문·숫자: 글자 수는 64자 이하지만 bcrypt 한도(72바이트)를 넘는다.
    response = await client.post(
        "/auth/signup",
        json={"email": "long@example.com", "password": "가" * 30 + "abc123", "nickname": "긴비번"},
    )

    assert response.status_code == 422
    assert "72바이트" in response.json()["details"][0]["message"]


async def test_login_issues_token_that_works_for_me(client):
    await signup(client, "me@example.com", "나나")
    headers = await login(client, "me@example.com")

    response = await client.get("/auth/me", headers=headers)

    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"


async def test_login_failure_does_not_reveal_whether_email_exists(client):
    await signup(client, "exists@example.com")

    wrong_password = await client.post(
        "/auth/login", data={"username": "exists@example.com", "password": "wrong1234"}
    )
    unknown_email = await client.post(
        "/auth/login", data={"username": "nobody@example.com", "password": PASSWORD}
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    assert wrong_password.json()["code"] == "INVALID_CREDENTIALS"


async def test_login_with_password_over_72_bytes_is_401_not_500(client):
    await signup(client, "exists@example.com")

    response = await client.post(
        "/auth/login", data={"username": "exists@example.com", "password": "가" * 30}
    )

    assert response.status_code == 401


async def test_me_without_token(client):
    response = await client.get("/auth/me")

    assert response.status_code == 401
    assert response.json()["code"] == "NOT_AUTHENTICATED"
    assert response.headers["www-authenticate"] == "Bearer"


async def test_me_with_tampered_token(client):
    response = await client.get("/auth/me", headers={"Authorization": "Bearer not.a.jwt"})

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_TOKEN"


async def test_me_with_expired_token(client):
    user = await signup(client, "old@example.com")
    token = create_access_token(user["id"], expires_delta=timedelta(seconds=-1))

    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_EXPIRED"
