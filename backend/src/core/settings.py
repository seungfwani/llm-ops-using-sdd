from __future__ import annotations

from functools import lru_cache
from pydantic import AnyUrl, AnyHttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
    
    database_url: AnyUrl = "postgresql+psycopg://llmops:password@localhost:5432/llmops"
    sqlalchemy_echo: bool = False
    redis_url: AnyUrl = "redis://localhost:6379/0"
    object_store_endpoint: AnyUrl = "http://localhost:9000"
    object_store_access_key: str = "llmops"
    object_store_secret_key: SecretStr = SecretStr("llmops-secret")
    object_store_secure: bool = False
    prometheus_namespace: str = "llm_ops"
    default_required_role: str = "llm-ops-user"
    kubeconfig_path: str | None = None


@lru_cache()
def get_settings() -> Settings:
    return Settings()

