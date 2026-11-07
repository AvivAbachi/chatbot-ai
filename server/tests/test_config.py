from app.config import Settings


def test_remote_qdrant_api_key_is_optional(monkeypatch):
    monkeypatch.delenv("QDRANT_API_KEY", raising=False)
    settings = Settings(
        _env_file=None,
        llm_base_url="http://localhost:8888/v1",
        llm_api_key="test",
        qdrant_url="https://qdrant.example.com",
    )
    assert settings.qdrant_api_key is None


def test_empty_qdrant_api_key_is_treated_as_missing(monkeypatch):
    monkeypatch.setenv("QDRANT_API_KEY", "")
    settings = Settings(
        _env_file=None,
        llm_base_url="http://localhost:8888/v1",
        llm_api_key="test",
        qdrant_url="https://qdrant.example.com",
    )
    assert settings.qdrant_api_key is None


def test_embedding_dimensions_can_be_configured(monkeypatch):
    monkeypatch.setenv("LLM_EMBEDDING_DIMENSIONS", "1536")
    settings = Settings(
        _env_file=None,
        llm_base_url="http://localhost:8888/v1",
        llm_api_key="test",
    )
    assert settings.llm_embedding_dimensions == 1536
