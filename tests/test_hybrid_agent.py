import json
from types import SimpleNamespace

from app.chat import hybrid_agent, service


def setup_sources(monkeypatch, *, rows=None, passages=None):
    rows = [[123]] if rows is None else rows
    passages = [{'source': 'norma.pdf', 'page': 2, 'text': 'Contexto'}] if passages is None else passages
    monkeypatch.setattr(hybrid_agent, 'retrieve', lambda q, h: passages)
    sql_result = {
        'answer': 'Público: 123', 'sql': 'SELECT 123 AS publico',
        'columns': ['publico'], 'rows': rows, 'rowCount': len(rows), 'error': None,
    }
    calls = []

    def sql(q, m, h):
        calls.append((q, m, h))
        return sql_result.copy()

    monkeypatch.setattr(hybrid_agent, 'answer_sql', sql)
    payloads = []

    class Model:
        def invoke(self, messages):
            payloads.append(json.loads(messages[1]['content']))
            return SimpleNamespace(content=[{'text': 'Análise integrada com fontes'}])

    monkeypatch.setattr(hybrid_agent, 'build_chat_model', lambda m: Model())
    return calls, payloads


def test_service_combines_both_sources_and_preserves_table(monkeypatch):
    calls, payloads = setup_sources(monkeypatch)
    question = 'Compare os dados da base de bilheteria com os documentos da legislação'
    result = service.answer_chat_question(question, history=['Em 2024'])
    assert calls == [(question, None, ['Em 2024'])]
    assert payloads[0]['perguntas_anteriores'] == ['Em 2024']
    assert payloads[0]['trechos_documentais'][0]['text'] == 'Contexto'
    assert payloads[0]['base_sql']['rows'] == [[123]]
    assert result['answer'] == 'Análise integrada com fontes'
    assert result['sql'] == 'SELECT 123 AS publico'
    assert result['columns'] == ['publico']
    assert result['rows'] == [[123]]
    assert result['rowCount'] == 1
    assert result['sources'] == [{'source': 'norma.pdf', 'page': 2}]


def test_no_documents_still_queries_sql(monkeypatch):
    calls, payloads = setup_sources(monkeypatch, passages=[])
    result = hybrid_agent.answer_question('Qual o público?')
    assert calls
    assert result['sql']
    assert payloads[0]['limitacoes'] == ['Não foram encontrados trechos documentais relevantes.']


def test_sql_failure_still_uses_documents(monkeypatch):
    _, payloads = setup_sources(monkeypatch)

    def fail(*args):
        raise RuntimeError('database unavailable')

    monkeypatch.setattr(hybrid_agent, 'answer_sql', fail)
    result = hybrid_agent.answer_question('Pergunta')
    assert result['error'] is None
    assert result['sql'] is None
    assert result['sources']
    assert payloads[0]['limitacoes']
    assert payloads[0]['trechos_documentais']


def test_document_failure_still_queries_sql(monkeypatch):
    calls, payloads = setup_sources(monkeypatch)

    def fail(*args):
        raise RuntimeError('unreadable document')

    monkeypatch.setattr(hybrid_agent, 'retrieve', fail)
    result = hybrid_agent.answer_question('Pergunta')
    assert calls
    assert result['sql']
    assert result['sources'] == []
    assert 'recuperação' in payloads[0]['limitacoes'][0]


def test_preview_is_bounded_without_truncating_returned_table(monkeypatch):
    rows = [[i] for i in range(30)]
    _, payloads = setup_sources(monkeypatch, rows=rows)
    result = hybrid_agent.answer_question('Pergunta')
    assert len(payloads[0]['base_sql']['rows']) == hybrid_agent.TOOL_PREVIEW_ROWS
    assert payloads[0]['base_sql']['previa_truncada'] is True
    assert result['rows'] == rows
    assert result['rowCount'] == 30


def test_synthesis_failure_preserves_sql_with_explicit_warning(monkeypatch):
    setup_sources(monkeypatch)

    def fail(*args):
        raise RuntimeError('provider unavailable')

    monkeypatch.setattr(hybrid_agent, 'build_chat_model', fail)
    result = hybrid_agent.answer_question('Pergunta')
    assert result['rows'] == [[123]]
    assert result['error'] is None
    assert 'Público: 123' in result['answer']
    assert 'Não foi possível produzir a análise integrada' in result['answer']


def test_empty_sql_result_is_reported_as_limitation(monkeypatch):
    _, payloads = setup_sources(monkeypatch, rows=[])
    hybrid_agent.answer_question('Pergunta')
    assert 'A consulta SQL não retornou linhas.' in payloads[0]['limitacoes']


def test_unsuccessful_sql_is_not_used_as_evidence(monkeypatch):
    _, payloads = setup_sources(monkeypatch)
    monkeypatch.setattr(hybrid_agent, 'answer_sql', lambda *args: {
        'answer': 'Resposta sem evidência', 'sql': None, 'error': 'validation error',
    })
    result = hybrid_agent.answer_question('Pergunta')
    assert result['error'] is None
    assert payloads[0]['base_sql']['resposta_preliminar'] == ''
    assert 'Não foi possível executar uma consulta SQL válida.' in payloads[0]['limitacoes']


def test_sql_agent_executes_guarded_query_with_history(monkeypatch):
    import duckdb

    from app.chat import nl2sql_agent

    con = duckdb.connect(':memory:')
    con.execute('CREATE TABLE bilheteria (publico INTEGER)')
    con.execute('INSERT INTO bilheteria VALUES (100), (23)')
    monkeypatch.setattr(nl2sql_agent, 'connect_ancine', lambda: con)
    monkeypatch.setattr(nl2sql_agent, 'build_chat_model', lambda m: object())
    requests = []

    def create_agent(*, model, tools, system_prompt):
        class Agent:
            def invoke(self, request, config):
                requests.append(json.loads(request['messages'][0]['content']))
                output = tools[0].invoke({'sql': 'SELECT SUM(publico) AS publico FROM bilheteria'})
                assert '123' in output
                return {'messages': [SimpleNamespace(content='Público: 123')]}
        return Agent()

    monkeypatch.setattr(nl2sql_agent, 'create_agent', create_agent)
    result = nl2sql_agent.answer_question('E o público?', history=['Cinema brasileiro'])
    assert result['rows'] == [[123]]
    assert result['columns'] == ['publico']
    assert result['sql']
    assert result['error'] is None
    assert requests == [{
        'pergunta_atual': 'E o público?', 'perguntas_anteriores': ['Cinema brasileiro'],
    }]
