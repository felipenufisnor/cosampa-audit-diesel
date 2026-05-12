from __future__ import annotations

from audit_diesel.ai.provider import OfflineProvider, get_provider
from audit_diesel.config import Settings


def test_settings_ai_defaults(monkeypatch):
    for key in (
        "LLM_MODEL",
        "LLM_FALLBACK_MODEL",
        "AUDIT_AI_OFFLINE",
        "DEMO_MODE",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = Settings(_env_file=None)

    assert settings.llm_model == "qwen/qwen3-32b"
    assert settings.llm_fallback_model == "deepseek/deepseek-chat"
    assert settings.audit_ai_offline is False
    assert settings.demo_mode == "off"


def test_provider_uses_offline_when_openrouter_has_no_key():
    settings = Settings(
        _env_file=None,
        llm_provider="openrouter",
        llm_base_url="https://openrouter.ai/api/v1",
        llm_api_key=None,
        audit_ai_offline=False,
    )

    provider = get_provider(settings)

    assert isinstance(provider, OfflineProvider)
    assert provider.info.offline is True


def test_assistant_health_missing_key():
    from audit_diesel.api import main

    main._AI_PROBE_CACHE.clear()
    settings = Settings(
        _env_file=None,
        llm_provider="openrouter",
        llm_base_url="https://openrouter.ai/api/v1",
        llm_api_key=None,
        audit_ai_offline=False,
    )

    health = main._assistant_health(settings)

    assert health.status == "missing_key"
    assert health.can_answer_free_text is False


def test_assistant_health_available_with_online_provider(monkeypatch):
    from audit_diesel.api import main

    class HealthyChatClient:
        def __init__(self, *args, **kwargs):
            pass

        def chat(self, **_kwargs):
            return object()

    monkeypatch.setattr("audit_diesel.ai.client.ChatClient", HealthyChatClient)
    main._AI_PROBE_CACHE.clear()
    settings = Settings(
        _env_file=None,
        llm_provider="mock",
        llm_base_url="https://mock.example/v1",
        llm_api_key="test-key",
        audit_ai_offline=False,
    )

    health = main._assistant_health(settings)

    assert health.status == "available"
    assert health.can_answer_free_text is True
