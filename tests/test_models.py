from app.chat.models import list_model_options, model_is_available, resolve_model_id


def test_models_without_credentials_are_hidden(monkeypatch):
    for key in (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "DEEPSEEK_API_KEY",
        "QWEN_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("CHAT_SHOW_UNAVAILABLE_MODELS", raising=False)
    assert list_model_options() == []
    assert not model_is_available(resolve_model_id(None))
