"""Registro dos modelos de IA disponíveis para o chat — cada opção sabe
construir seu próprio LangChain chat model. Adicionar um modelo novo é
adicionar uma entrada em MODEL_OPTIONS; nl2sql_agent.py e o endpoint em
server.py não precisam saber a diferença entre os provedores.

Conjunto de modelos trazido de ../oca (mesmo painel, projeto irmão) — só
não trouxemos a ANTHROPIC_API_KEY de lá, já que a chave configurada aqui
já funciona."""
import os

from langchain_anthropic import ChatAnthropic
from langchain_deepseek import ChatDeepSeek
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

_FALLBACK_MODEL_ID = "claude-haiku-4-5-20251001"


# ── Anthropic ────────────────────────────────────────────────────────────────
def _claude_haiku_4_5():
    return ChatAnthropic(model="claude-haiku-4-5-20251001")


def _claude_sonnet_5():
    return ChatAnthropic(model="claude-sonnet-5")


def _claude_opus_5():
    return ChatAnthropic(model="claude-opus-5")


# ── OpenAI ───────────────────────────────────────────────────────────────────
def _gpt_4o_mini():
    return ChatOpenAI(model="gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY"))


def _gpt_4o():
    return ChatOpenAI(model="gpt-4o", api_key=os.getenv("OPENAI_API_KEY"))


def _gpt_4_1():
    return ChatOpenAI(model="gpt-4.1", api_key=os.getenv("OPENAI_API_KEY"))


# ── Google Gemini ────────────────────────────────────────────────────────────
def _gemini_2_5_flash():
    return ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.getenv("GEMINI_API_KEY"))


def _gemini_2_5_flash_lite():
    return ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", google_api_key=os.getenv("GEMINI_API_KEY"))


def _gemini_2_5_pro():
    return ChatGoogleGenerativeAI(model="gemini-2.5-pro", google_api_key=os.getenv("GEMINI_API_KEY"))


# ── DeepSeek ─────────────────────────────────────────────────────────────────
def _deepseek_v3():
    return ChatDeepSeek(model="deepseek-chat")  # DeepSeek-V3, lê DEEPSEEK_API_KEY


def _deepseek_r1():
    return ChatDeepSeek(model="deepseek-reasoner")  # DeepSeek-R1, lê DEEPSEEK_API_KEY


# ── Qwen ─────────────────────────────────────────────────────────────────────
def _qwen_coder_32b():
    # Qwen não tem pacote LangChain dedicado — usa a API compatível com OpenAI
    # (Alibaba Cloud Model Studio/DashScope por padrão; QWEN_BASE_URL troca o
    # provedor). qwen2.5-coder-32b-instruct é um modelo legado que só existe
    # na região China (Pequim) do DashScope — a região internacional
    # (dashscope-intl) devolve 404 model_not_found para ele.
    return ChatOpenAI(
        model=os.getenv("QWEN_MODEL", "qwen2.5-coder-32b-instruct"),
        api_key=os.getenv("QWEN_API_KEY"),
        base_url=os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    )


# id -> {label exibido no seletor, provider (agrupa o <select> no front-end),
# build() -> BaseChatModel}
MODEL_OPTIONS = {
    # Anthropic
    "claude-haiku-4-5-20251001":  {"label": "Claude Haiku 4.5",   "build": _claude_haiku_4_5,  "provider": "Anthropic"},
    "claude-sonnet-5":             {"label": "Claude Sonnet 5",    "build": _claude_sonnet_5,   "provider": "Anthropic"},
    "claude-opus-5":               {"label": "Claude Opus 5",      "build": _claude_opus_5,     "provider": "Anthropic"},
    # OpenAI
    "gpt-4o-mini":                  {"label": "GPT-4o Mini",         "build": _gpt_4o_mini,       "provider": "OpenAI"},
    "gpt-4o":                       {"label": "GPT-4o",              "build": _gpt_4o,            "provider": "OpenAI"},
    "gpt-4.1":                      {"label": "GPT-4.1",             "build": _gpt_4_1,           "provider": "OpenAI"},
    # Gemini
    "gemini-2.5-flash":              {"label": "Gemini 2.5 Flash",      "build": _gemini_2_5_flash,      "provider": "Google"},
    "gemini-2.5-flash-lite":         {"label": "Gemini 2.5 Flash Lite", "build": _gemini_2_5_flash_lite, "provider": "Google"},
    "gemini-2.5-pro":                {"label": "Gemini 2.5 Pro",        "build": _gemini_2_5_pro,        "provider": "Google"},
    # DeepSeek
    "deepseek-chat":                {"label": "DeepSeek V3",         "build": _deepseek_v3,       "provider": "DeepSeek"},
    "deepseek-reasoner":            {"label": "DeepSeek R1",         "build": _deepseek_r1,       "provider": "DeepSeek"},
    # Qwen
    "qwen2.5-coder-32b-instruct":   {"label": "Qwen 2.5 Coder 32B", "build": _qwen_coder_32b,    "provider": "Alibaba"},
}

# CHAT_LLM_MODEL escolhe o modelo padrão (pré-selecionado no front-end); se
# vier vazio ou apontar para um id que não existe em MODEL_OPTIONS, cai no
# fallback abaixo em vez de quebrar o boot da aplicação.
DEFAULT_MODEL_ID = os.getenv("CHAT_LLM_MODEL") or _FALLBACK_MODEL_ID
if DEFAULT_MODEL_ID not in MODEL_OPTIONS:
    DEFAULT_MODEL_ID = _FALLBACK_MODEL_ID


def resolve_model_id(model_id: str | None) -> str:
    return model_id if model_id in MODEL_OPTIONS else DEFAULT_MODEL_ID


def build_chat_model(model_id: str | None):
    return MODEL_OPTIONS[resolve_model_id(model_id)]["build"]()


def list_model_options() -> list[dict]:
    return [
        {
            "id": model_id,
            "label": opt["label"],
            "provider": opt.get("provider", "Outro"),
            "default": model_id == DEFAULT_MODEL_ID,
        }
        for model_id, opt in MODEL_OPTIONS.items()
    ]
