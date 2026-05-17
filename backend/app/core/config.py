from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Warehouse Optimization & Smart Routing API"
    database_url: str = Field(
        default="postgresql+psycopg://supplychain:supplychain@localhost:5432/supplychain",
        alias="DATABASE_URL",
    )
    secret_key: str = Field(default="dev-secret-change-me", alias="SECRET_KEY")
    algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=480, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="CORS_ORIGINS",
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

