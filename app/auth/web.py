"""OIDC login and signed browser sessions, without a user database."""

import logging
import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlsplit

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from app.auth.policy import PolicyError, is_allowed, load_policy

ROOT = Path(__file__).resolve().parents[2]
SESSION_TTL = 8 * 60 * 60
logger = logging.getLogger(__name__)
router = APIRouter()
oauth = OAuth()


def base_url():
    value = os.getenv("AUTH_BASE_URL", "http://localhost:8080").rstrip("/")
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username
    ):
        raise RuntimeError("AUTH_BASE_URL deve ser uma origem HTTP(S), sem caminho.")
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise RuntimeError("AUTH_BASE_URL requer HTTPS fora do ambiente local.")
    return value


def client(provider, organization=None):
    if provider not in {"google", "microsoft"}:
        raise HTTPException(404, "Provedor desconhecido.")
    prefix = provider.upper()
    client_id = os.getenv(f"{prefix}_CLIENT_ID")
    secret = os.getenv(f"{prefix}_CLIENT_SECRET")
    if not client_id or not secret:
        raise HTTPException(503, "Este provedor de login ainda não foi configurado.")
    if provider == "google":
        metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
    else:
        tenant = load_policy()[1].get(organization)
        if not tenant:
            raise HTTPException(403, "Organização Microsoft não autorizada.")
        metadata_url = (
            f"https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration"
        )
    return oauth.register(
        provider if provider == "google" else f"microsoft_{tenant}",
        overwrite=True,
        client_id=client_id,
        client_secret=secret,
        server_metadata_url=metadata_url,
        client_kwargs={"scope": "openid profile email", "code_challenge_method": "S256"},
    )


@router.get("/auth/providers")
def providers():
    allowed, tenants = load_policy()
    return {
        "google": bool(
            allowed and os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET")
        ),
        "microsoft": sorted(tenants)
        if os.getenv("MICROSOFT_CLIENT_ID") and os.getenv("MICROSOFT_CLIENT_SECRET")
        else [],
    }


@router.get("/auth/login/{provider}")
async def login(provider: str, request: Request, organization: str | None = None):
    provider_client = client(provider, organization)
    request.session.clear()
    if provider == "microsoft":
        request.session["microsoft_organization"] = organization
    return await provider_client.authorize_redirect(
        request,
        f"{base_url()}/auth/callback/{provider}",
    )


@router.get("/auth/callback/{provider}")
async def callback(provider: str, request: Request):
    try:
        # Dentro do try: uma sessão já consumida/expirada (ex.: callback
        # recarregado após o login já ter concluído) não deve virar um erro
        # cru — cai no mesmo tratamento de "não foi possível entrar" abaixo.
        provider_client = client(provider, request.session.get("microsoft_organization"))
        # Authlib checks state, signature, issuer, audience, expiry and nonce.
        token = await provider_client.authorize_access_token(request)
        claims = token.get("userinfo")
        if not claims or not claims.get("iss") or not claims.get("sub"):
            raise ValueError("Missing validated identity")
        user = {
            "provider": provider,
            "issuer": claims["iss"],
            "subject": claims["sub"],
            "name": str(claims.get("name") or "Usuário")[:255],
            "email": str(claims.get("email") or ""),
            "email_verified": claims.get("email_verified") is True,
            "hd": claims.get("hd") or "",
            "tid": claims.get("tid"),
            "oid": claims.get("oid"),
            "acct": claims.get("acct"),
        }
    except Exception:
        # Never log tokens, authorization codes or provider profile data.
        logger.warning("OIDC login failed for %s", provider)
        request.session.clear()
        return RedirectResponse("/login?error=login", status_code=303)
    request.session.clear()
    if not is_allowed(user, load_policy()):
        return RedirectResponse("/login?error=domain", status_code=303)
    request.session.update(user=user, expires_at=int(time.time()) + SESSION_TTL)
    return RedirectResponse("/", status_code=303)


@router.get("/auth/me")
def me(request: Request):
    return {k: request.state.user[k] for k in ("provider", "name", "email")}


@router.post("/auth/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/login", include_in_schema=False)
def login_page():
    return FileResponse(ROOT / "static/auth/login.html")


@router.get("/account", include_in_schema=False)
def account_page():
    return FileResponse(ROOT / "static/auth/account.html")


def install_auth(app):
    secret = os.getenv("AUTH_SESSION_SECRET")
    if secret and len(secret) < 32:
        raise RuntimeError("AUTH_SESSION_SECRET deve ter pelo menos 32 caracteres.")
    if os.getenv("K_SERVICE") and (not secret or not os.getenv("AUTH_BASE_URL")):
        raise RuntimeError("Configure AUTH_BASE_URL e AUTH_SESSION_SECRET no Cloud Run.")
    app.include_router(router)

    @app.exception_handler(PolicyError)
    async def policy_error(request, error):
        return JSONResponse(
            {"detail": "A configuração de acesso está indisponível."}, status_code=503
        )

    @app.middleware("http")
    async def require_login(request: Request, call_next):
        path = request.url.path
        public = path in {
            "/login",
            "/auth/providers",
            "/health",
            "/health/live",
            "/health/ready",
        } or path.startswith(("/auth/login/", "/auth/callback/", "/css/", "/js/", "/static/"))
        user = request.session.get("user")
        expires_at = request.session.get("expires_at", 0)
        if not isinstance(expires_at, (int, float)) or expires_at <= time.time():
            user = None
            if "user" in request.session:
                request.session.clear()
        try:
            if user and not is_allowed(user, load_policy()):
                request.session.clear()
                user = None
        except PolicyError:
            request.session.clear()
            return JSONResponse(
                {"detail": "A configuração de acesso está indisponível."},
                status_code=503,
                headers={"Cache-Control": "no-store"},
            )
        request.state.user = user
        if public:
            response = await call_next(request)
        elif not user:
            response = (
                JSONResponse({"detail": "Faça login para continuar."}, status_code=401)
                if path.startswith(("/api/", "/auth/"))
                else RedirectResponse("/login", status_code=303)
            )
        elif (
            request.method not in {"GET", "HEAD", "OPTIONS"}
            and request.headers.get("origin") != base_url()
        ):
            response = JSONResponse({"detail": "Origem da solicitação inválida."}, status_code=403)
        else:
            response = await call_next(request)
        if not path.startswith(("/css/", "/js/", "/static/vendor/")):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    # Added last so the signed session is available to the authentication middleware.
    app.add_middleware(
        SessionMiddleware,
        secret_key=secret or secrets.token_urlsafe(48),
        session_cookie="scb_session",
        max_age=SESSION_TTL,
        same_site="lax",
        https_only=base_url().startswith("https:"),
    )
