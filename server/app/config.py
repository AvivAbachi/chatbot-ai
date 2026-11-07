from functools import lru_cache

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    llm_base_url: str
    llm_api_key: str = ""
    llm_model: str | None = None
    llm_embedd_model: str | None = None
    llm_embedding_dimensions: int = Field(default=768, gt=0)

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "document_chunks"
    force_rebuild: bool = False

    app_env: str = "development"
    log_level: str = "INFO"
    rate_limit: str = "20/minute"
    max_retries: int = 3

    @field_validator("qdrant_api_key", mode="before")
    @classmethod
    def empty_api_key_is_none(cls, value):
        return value or None

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
