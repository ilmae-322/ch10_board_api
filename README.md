# 게시판 API (FastAPI + SQLAlchemy + PostgreSQL)

JWT 인증·인가가 적용된 RESTful 게시판 API입니다. PostgreSQL과 SQLAlchemy(비동기 ORM)로 데이터를 관리하고, AWS EC2에 Docker Compose로 배포했습니다.

## 배포 주소

| 항목 | 주소 |
|---|---|
| 서비스 | http://<퍼블릭 IP> |
| Swagger UI | http://<퍼블릭 IP>/docs |

### Swagger UI에서 테스트하는 순서

1. `POST /auth/signup`으로 회원가입 (비밀번호는 영문과 숫자를 포함해 8자 이상)
2. 오른쪽 위 **Authorize** 버튼 클릭 → `username`에 이메일, `password`에 비밀번호 입력
3. `POST /posts`로 게시글 작성
4. `PATCH /posts/{post_id}`, `DELETE /posts/{post_id}`로 수정·삭제 (작성자 본인만 가능)
5. 다른 계정으로 Authorize한 뒤 위 게시글을 수정하면 `403`이 반환됩니다.

## 기술 스택

| 구분 | 사용 기술 |
|---|---|
| 프레임워크 | FastAPI (비동기) |
| 데이터베이스 | PostgreSQL 16 |
| ORM | SQLAlchemy 2.0 (AsyncSession + asyncpg) |
| 검증·직렬화 | Pydantic v2 |
| 인증 | JWT (PyJWT), 비밀번호 해싱 (bcrypt) |
| 문서화 | OpenAPI (Swagger UI) |
| 배포 | AWS EC2, Docker Compose |
| 패키지 관리 | uv |

## 프로젝트 구조

```
app/
├── main.py              # 앱 생성, 미들웨어, 예외 핸들러, 라우터 등록
├── database.py          # 비동기 엔진, 세션
├── deps.py              # 공통 의존성 (DB 세션, 현재 사용자)
├── core/
│   ├── config.py        # 환경 변수 설정
│   ├── security.py      # 비밀번호 해싱, JWT 발급·검증
│   ├── exceptions.py    # 커스텀 예외, 전역 예외 핸들러
│   ├── middleware.py    # 요청 로깅, 처리 시간 측정
│   └── cache.py         # 인메모리 TTL 캐시
├── models/              # SQLAlchemy 모델 (User, Post)
├── schemas/             # Pydantic 요청·응답 스키마
└── routers/             # 엔드포인트 (auth, posts)
```

## API 명세

| 기능 | 메서드 | 경로 | 인증 | 성공 코드 |
|---|---|---|---|---|
| 회원가입 | POST | `/auth/signup` | 불필요 | 201 |
| 로그인 (JWT 발급) | POST | `/auth/login` | 불필요 | 200 |
| 내 정보 조회 | GET | `/auth/me` | 필요 | 200 |
| 게시글 목록 | GET | `/posts?page=1&size=10&keyword=` | 불필요 | 200 |
| 게시글 단건 | GET | `/posts/{post_id}` | 불필요 | 200 |
| 게시글 작성 | POST | `/posts` | 필요 | 201 |
| 게시글 수정 | PATCH | `/posts/{post_id}` | 필요 (작성자) | 200 |
| 게시글 삭제 | DELETE | `/posts/{post_id}` | 필요 (작성자 또는 관리자) | 204 |
| 이미지 업로드 | POST | `/posts/{post_id}/image` | 필요 (작성자) | 200 |
| 상태 확인 | GET | `/health` | 불필요 | 200 |

### REST 설계 원칙

- URL은 자원(명사)만 나타내고 동작은 HTTP 메서드로 표현합니다. (`POST /posts`, `DELETE /posts/1`)
- 부분 수정은 `PATCH`, 생성은 `201 Created`, 삭제는 본문 없는 `204 No Content`를 사용합니다.
- 목록은 쿼리 매개변수로 페이지네이션(`page`, `size`)과 검색(`keyword`)을 지원합니다.

### 공통 오류 응답

모든 오류는 같은 형식으로 응답합니다.

```json
{
  "code": "VALIDATION_ERROR",
  "message": "입력값이 올바르지 않습니다.",
  "details": [
    { "field": "password", "message": "비밀번호는 영문과 숫자를 모두 포함해야 합니다." }
  ]
}
```

| 상태 코드 | code | 상황 |
|---|---|---|
| 400 | `INVALID_FILE` | 허용되지 않은 파일 형식, 빈 파일 |
| 401 | `NOT_AUTHENTICATED` | 토큰 없음 |
| 401 | `INVALID_TOKEN` | 위변조되었거나 형식이 잘못된 토큰 |
| 401 | `TOKEN_EXPIRED` | 만료된 토큰 |
| 401 | `INVALID_CREDENTIALS` | 이메일 또는 비밀번호 불일치 |
| 403 | `PERMISSION_DENIED` | 작성자가 아닌 사용자의 수정·삭제 |
| 404 | `POST_NOT_FOUND` | 존재하지 않는 게시글 |
| 409 | `EMAIL_ALREADY_EXISTS` | 이미 가입된 이메일 |
| 413 | `FILE_TOO_LARGE` | 5MB 초과 파일 |
| 422 | `VALIDATION_ERROR` | 입력값 검증 실패 |

## 구현 내용

### 데이터 검증과 직렬화 (Pydantic)

- 요청 스키마(`UserCreate`, `PostCreate`, `PostUpdate`)와 응답 스키마(`UserResponse`, `PostResponse`, `PostListResponse`)를 분리했습니다. 응답에는 비밀번호 해시가 포함되지 않습니다.
- 커스텀 검증: 비밀번호는 영문과 숫자를 모두 포함, 제목과 내용은 공백만으로 작성 불가, 수정 요청은 항목을 하나 이상 포함해야 합니다.
- 검증 오류는 전역 예외 핸들러에서 공통 오류 형식으로 변환합니다.

### ORM과 데이터베이스 (SQLAlchemy)

- `User`와 `Post`는 1:N 관계이며 `relationship`을 양방향으로 정의했습니다. 회원이 삭제되면 게시글도 함께 삭제됩니다(`ON DELETE CASCADE`).
- 목록과 단건 조회에서 `joinedload`로 작성자를 함께 가져와 N+1 쿼리를 방지했습니다.
- 목록은 `OFFSET`/`LIMIT`으로 페이지네이션하고, 정렬 컬럼(`created_at`)과 외래 키(`author_id`)에 인덱스를 두었습니다.

### 인증과 인가 (JWT)

- 인증: 로그인 시 만료 시간(`exp`)이 포함된 액세스 토큰을 발급하고, 보호된 API는 `Authorization: Bearer <토큰>` 헤더를 검증합니다.
- 인가: 게시글 수정과 이미지 업로드는 작성자만, 삭제는 작성자 또는 관리자만 가능합니다. 권한이 없으면 `403`을 반환합니다.
- 비밀번호는 bcrypt로 해싱해 저장합니다.
- 토큰 만료(`TOKEN_EXPIRED`)와 위변조(`INVALID_TOKEN`)를 구분해 응답합니다.
- JWT 서명 키와 DB 접속 정보는 환경 변수(`.env`)로 관리하며 저장소에 올리지 않습니다.
- 로그인 실패 시 이메일 오류와 비밀번호 오류를 같은 메시지로 응답해 계정 존재 여부를 노출하지 않습니다.

### 서비스 구성과 운영

| 기능 | 구현 | 확인 방법 |
|---|---|---|
| 비동기 | 모든 엔드포인트와 DB 접근을 `async`로 처리 (AsyncSession, asyncpg, aiofiles) | 전체 API |
| 업로드 | `POST /posts/{post_id}/image`. 형식(JPEG, PNG, GIF, WebP)과 크기(5MB) 검증, 서버가 생성한 파일명으로 저장 | 업로드 후 응답의 `image_url` 경로로 접속 |
| 캐싱 | 게시글 목록을 30초 동안 인메모리 캐시, 글 작성·수정·삭제 시 무효화 | 목록을 두 번 조회하면 응답 헤더 `X-Cache`가 `MISS` → `HIT` |
| 미들웨어 | CORS, 요청 로깅과 처리 시간 측정 | 모든 응답의 `X-Process-Time` 헤더, 서버 로그 |
| 예외 처리 | 커스텀 예외와 전역 핸들러로 오류 형식 통일, 예상하지 못한 오류는 내부 정보를 숨기고 `500` 응답 | 위 오류 응답 표 |

## 로컬 실행

```bash
cp .env.example .env          # JWT_SECRET_KEY를 임의의 값으로 교체
docker compose up -d --build  # http://localhost/docs
```

Docker 없이 실행하려면 PostgreSQL을 준비하고 `.env`의 `DATABASE_URL` 호스트를 `localhost`로 바꾼 뒤 다음을 실행합니다.

```bash
uv sync
uv run uvicorn app.main:app --reload   # http://localhost:8000/docs
```

테이블은 서버 시작 시 자동으로 생성됩니다.

## AWS EC2 배포

1. EC2 인스턴스 생성 (Ubuntu 24.04), 보안 그룹 인바운드 규칙에 **HTTP(80)** 과 SSH(22) 허용
2. 서버 접속 후 Docker 설치

   ```bash
   sudo apt update
   sudo apt install -y docker.io docker-compose-v2 git
   ```

3. 코드 내려받기와 환경 변수 설정

   ```bash
   git clone <저장소 URL> board-api
   cd board-api
   cp .env.example .env
   nano .env    # JWT_SECRET_KEY, POSTGRES_PASSWORD(및 DATABASE_URL의 비밀번호) 변경
   ```

4. 실행

   ```bash
   sudo docker compose up -d --build
   sudo docker compose logs -f api   # 로그 확인 (Ctrl+C로 종료)
   ```

5. 브라우저에서 `http://<퍼블릭 IP>/docs` 접속

`restart: unless-stopped` 설정으로 서버가 재부팅되어도 컨테이너가 자동으로 다시 실행됩니다.

### 관리자 지정

```bash
sudo docker compose exec db psql -U board -d board \
  -c "update users set role = 'admin' where email = 'admin@example.com';"
```
