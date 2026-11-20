"""환경 변수 기반 설정. 비밀 값(JWT 키, DB 접속 정보)은 코드에 두지 않고 .env에서 읽는다."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    cors_origins: str = "*"
    cache_ttl_seconds: int = 30

    upload_dir: str = "uploads"
    max_upload_bytes: int = 5 * 1024 * 1024  # 5MB

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
