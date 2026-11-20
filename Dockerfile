FROM python:3.13-slim

# uv 설치 (공식 이미지에서 실행 파일만 복사)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# 의존성을 먼저 설치해 코드만 바뀌었을 때 캐시를 재사용한다.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app ./app
RUN mkdir -p uploads

EXPOSE 8000

# 0.0.0.0으로 실행해야 컨테이너 밖(외부)에서 접속할 수 있다.
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
