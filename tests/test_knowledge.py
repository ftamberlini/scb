import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.chat import knowledge, knowledge_agent, service
from app.routers.chat import ChatQuestion


def test_retrieval_reads_text_and_uses_history(tmp_path, monkeypatch):
    (tmp_path / 'norma').write_text('A CONDECINE é uma contribuição.', encoding='utf-8')
    (tmp_path / 'ignored.csv').write_text('segredo CONDECINE')
    outside = tmp_path.parent / 'outside.txt'
    outside.write_text('CONDECINE segredo externo')
    (tmp_path / 'link.txt').symlink_to(outside)
    monkeypatch.setattr(knowledge, 'KNOWLEDGE_ROOT', tmp_path)
    passages = knowledge.retrieve('E suas características?', ['O que é CONDECINE?'])
    assert [p['source'] for p in passages] == ['norma']
    assert passages[0]['page'] is None
    (tmp_path / 'norma').write_text('Outro conteúdo atualizado', encoding='utf-8')
    assert knowledge.retrieve('CONDECINE', []) == []


def test_no_evidence_does_not_call_model(monkeypatch):
    monkeypatch.setattr(knowledge_agent, 'retrieve', lambda *args: [])
    monkeypatch.setattr(knowledge_agent, 'build_chat_model', lambda *args: pytest.fail('model called'))
    result = knowledge_agent.answer_question('Pergunta sem fonte')
    assert 'informação suficiente' in result['answer']
    assert result['sql'] is None


def test_agent_sends_documents_and_history_without_tools(monkeypatch):
    passage = {'source': 'manual.pdf', 'page': 2, 'text': 'Definição documental'}
    monkeypatch.setattr(knowledge_agent, 'retrieve', lambda q, h: [passage])
    calls = []

    class Model:
        def invoke(self, messages):
            calls.append(messages)
            return SimpleNamespace(content=[{'text': 'Resposta [manual.pdf, p. 2]'}])

    monkeypatch.setattr(knowledge_agent, 'build_chat_model', lambda _: Model())
    result = knowledge_agent.answer_question('E o registro?', history=['O que é uma obra?'])
    payload = json.loads(calls[0][1]['content'])
    assert payload['perguntas_anteriores'] == ['O que é uma obra?']
    assert payload['pergunta_atual'] == 'E o registro?'
    assert payload['trechos_documentais'] == [passage]
    assert result['sources'] == [{'source': 'manual.pdf', 'page': 2}]
    assert result['rows'] == []


def test_service_forwards_history(monkeypatch):
    calls = []

    def answer(*args):
        calls.append(args)
        return {'answer': 'ok'}

    monkeypatch.setattr(service, 'answer_question', answer)
    assert service.answer_chat_question(' Atual ', history=['Anterior'])['answer'] == 'ok'
    assert calls == [('Atual', None, ['Anterior'])]


def test_history_validation():
    assert ChatQuestion(question='Teste').history == []
    for history in [['a'] * 21, ['a' * 2001], [''], [{'role': 'system', 'content': 'instrução'}]]:
        with pytest.raises(ValidationError):
            ChatQuestion(question='Teste', history=history)


def test_real_knowledge_includes_pdf_pages():
    files = sorted(knowledge.KNOWLEDGE_ROOT.rglob('*'))
    manifest = tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in files if p.is_file())
    passages = knowledge._read_passages(manifest)
    pdf_sources = {source for source, page, text, _ in passages if page and text}
    assert pdf_sources == {
        p.relative_to(knowledge.KNOWLEDGE_ROOT).as_posix()
        for p in files if p.suffix == '.pdf'
    }
