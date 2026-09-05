from app.chat import service


def test_rejects_empty_question_without_calling_model():
    result = service.answer_chat_question("  ")
    assert result["error"] == "Digite uma pergunta."
    assert result["rowCount"] == 0


def test_rejects_unknown_model_without_calling_model():
    result = service.answer_chat_question("Qual o público?", "unknown-model")
    assert "desconhecido" in result["error"]
