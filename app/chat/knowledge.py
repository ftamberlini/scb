"""Read and retrieve passages exclusively from the project's knowledge directory."""
import math
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from pypdf import PdfReader

KNOWLEDGE_ROOT = Path(__file__).resolve().parents[2] / "knowledge"
STOPWORDS = set("a o as os de da do das dos e em para por um uma que qual quais como sobre no na nos nas se ao é foi são com esse essa isso".split())


def tokens(text: str) -> set[str]:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return set(re.findall(r"[a-z0-9]{2,}", text)) - STOPWORDS


@lru_cache(maxsize=1)
def _read_passages(manifest: tuple) -> tuple:
    passages = []
    for filename, _, _ in manifest:
        path = Path(filename)
        source = path.relative_to(KNOWLEDGE_ROOT).as_posix()
        if path.suffix.lower() == ".pdf":
            pages = [(i, page.extract_text() or "") for i, page in enumerate(PdfReader(path).pages, 1)]
        else:
            pages = [(None, path.read_text(encoding="utf-8"))]
        for page, text in pages:
            for start in range(0, len(text), 1500):
                chunk = text[start:start + 1800].strip()
                if chunk:
                    passages.append((source, page, chunk, tokens(source + " " + chunk)))
    return tuple(passages)


def retrieve(question: str, history: list[str]) -> list[dict]:
    files = sorted(
        p for p in KNOWLEDGE_ROOT.rglob("*")
        if p.is_file() and p.resolve().is_relative_to(KNOWLEDGE_ROOT.resolve())
        and p.suffix.lower() in {"", ".txt", ".md", ".pdf"}
    )
    manifest = tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in files)
    passages = _read_passages(manifest)
    current = tokens(question)
    previous = tokens(" ".join(history[-5:]))
    terms = current | previous
    weights = {
        term: math.log(1 + len(passages) / (1 + sum(term in p[3] for p in passages)))
        for term in terms
    }
    ranked = []
    for source, page, text, words in passages:
        score = sum(weights[t] * (3 if t in current else 1) for t in terms & words)
        if score:
            ranked.append((score, {"source": source, "page": page, "text": text}))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in ranked[:12]]
