from app.chat import service


def test_rejects_empty_question_without_calling_model():
    result = service.answer_chat_question("  ")
    assert result["error"] == "Digite uma pergunta."
    assert result["rowCount"] == 0


def test_rejects_unknown_model_without_calling_model():
    result = service.answer_chat_question("Qual o público?", "unknown-model")
    assert "desconhecido" in result["error"]


def test_routes_to_sql_by_default():
    assert service.question_route("Qual foi o público de Bacurau?") == "sql"
    assert service.question_route("Filmes dirigidos por ana muylaert") == "sql"


def test_routes_conceptual_questions_to_documents():
    assert service.question_route("O que é a cota de tela?") == "documents"
    assert service.question_route("E como funciona?", ["Explique a CONDECINE"]) == "documents"


def test_only_routes_to_hybrid_on_explicit_cross_source_request():
    assert service.question_route(
        "Compare os dados da base de bilheteria com os documentos da legislação"
    ) == "hybrid"
    assert service.question_route("Compare a renda dos filmes por ano") == "sql"
