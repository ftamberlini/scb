import json
import time
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import web
from app.auth.policy import PolicyError, is_allowed, load_policy

TENANT = "11111111-2222-3333-4444-555555555555"


def google_claims(**changes):
    return {
        "iss": "https://accounts.google.com",
        "sub": "user-1",
        "name": "Pessoa",
        "email": "pessoa@ifrj.edu.br",
        "email_verified": True,
        "hd": "ifrj.edu.br",
        **changes,
    }


@pytest.fixture
def policy(tmp_path, monkeypatch):
    path = tmp_path / "auth.json"
    path.write_text(
        json.dumps(
            {
                "allowed_email_domains": ["ifrj.edu.br", "ancine.gov.br"],
                "microsoft_tenants": {"ifrj.edu.br": TENANT},
            }
        )
    )
    monkeypatch.setenv("AUTH_CONFIG_FILE", str(path))
    monkeypatch.setenv("AUTH_BASE_URL", "http://localhost:8080")
    monkeypatch.setenv("AUTH_SESSION_SECRET", "test-secret-" * 8)
    return path


@pytest.fixture
def client(policy):
    app = FastAPI()
    web.install_auth(app)

    @app.get("/")
    def index():
        return {"dashboard": True}

    @app.get("/api/data")
    def data():
        return {"data": True}

    return TestClient(app, base_url="http://localhost:8080")


def sign_in(client, monkeypatch, claims=None, provider="google"):
    async def authorize(request):
        return {"userinfo": google_claims() if claims is None else claims}

    monkeypatch.setattr(
        web, "client", lambda *args: SimpleNamespace(authorize_access_token=authorize)
    )
    return client.get("/auth/callback/" + provider, follow_redirects=False)


def test_anonymous_routes(client):
    assert client.get("/", follow_redirects=False).headers["location"] == "/login"
    assert client.get("/api/data").status_code == 401
    assert client.get("/auth/me").status_code == 401
    assert client.get("/login").status_code == 200


def test_allowed_login_cookie_and_account(client, monkeypatch):
    response = sign_in(client, monkeypatch)
    assert response.headers["location"] == "/"
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert client.get("/").status_code == 200
    assert client.get("/auth/me").json() == {
        "provider": "google",
        "name": "Pessoa",
        "email": "pessoa@ifrj.edu.br",
    }
    assert client.get("/api/data").headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "changes",
    [
        {"email": "pessoa@evil.test"},
        {"email": "pessoa@sub.ifrj.edu.br"},
        {"email": "pessoa@ifrj.edu.br.evil.test"},
        {"email_verified": False},
        {"hd": ""},
        {"hd": "evil.test"},
        {"email": ""},
    ],
)
def test_denied_domains_and_non_workspace_accounts(client, monkeypatch, changes):
    response = sign_in(client, monkeypatch, google_claims(**changes))
    assert response.headers["location"] == "/login?error=domain"
    assert client.get("/auth/me").status_code == 401


def test_removed_domain_invalidates_existing_session(client, policy, monkeypatch):
    sign_in(client, monkeypatch)
    policy.write_text(json.dumps({"allowed_email_domains": [], "microsoft_tenants": {}}))
    assert client.get("/auth/me").status_code == 401


def test_microsoft_requires_organization_member_and_matching_tenant(policy):
    user = {
        "provider": "microsoft",
        "email": "pessoa@ifrj.edu.br",
        "tid": TENANT,
        "oid": "member-1",
        "acct": 0,
    }
    assert is_allowed(user, load_policy())
    for changes in (
        {"tid": "wrong"},
        {"acct": 1},
        {"acct": None},
        {"oid": None},
        {"email": "pessoa@ancine.gov.br"},
    ):
        assert not is_allowed({**user, **changes}, load_policy())


def test_policy_fail_closed(policy):
    policy.write_text("{malformed")
    with pytest.raises(PolicyError):
        load_policy()


def test_invalid_config_denies_existing_session(client, policy, monkeypatch):
    sign_in(client, monkeypatch)
    policy.write_text("{}")
    assert client.get("/api/data").status_code == 503


def test_csrf_and_logout(client, monkeypatch):
    sign_in(client, monkeypatch)
    assert client.post("/auth/logout").status_code == 403
    assert client.post("/auth/logout", headers={"Origin": "https://evil.test"}).status_code == 403
    assert (
        client.post("/auth/logout", headers={"Origin": "http://localhost:8080"}).status_code == 200
    )
    assert client.get("/auth/me").status_code == 401


def test_expired_session(client, monkeypatch):
    sign_in(client, monkeypatch)
    now = time.time()
    monkeypatch.setattr(web.time, "time", lambda: now + web.SESSION_TTL + 1)
    assert client.get("/auth/me").status_code == 401


def test_tampered_cookie(client, monkeypatch):
    sign_in(client, monkeypatch)
    cookie = client.cookies.get("scb_session")
    client.cookies.clear()
    client.cookies.set("scb_session", cookie + "forged")
    assert client.get("/auth/me").status_code == 401


def test_failed_oidc_callback(client, monkeypatch):
    async def authorize(request):
        raise ValueError("Invalid state or signature")

    monkeypatch.setattr(
        web, "client", lambda *args: SimpleNamespace(authorize_access_token=authorize)
    )
    response = client.get("/auth/callback/google", follow_redirects=False)
    assert response.headers["location"] == "/login?error=login"
    assert client.get("/auth/me").status_code == 401


def test_real_oauth_rejects_missing_state(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-secret")
    response = client.get(
        "/auth/callback/google?code=untrusted&state=forged", follow_redirects=False
    )
    assert response.headers["location"] == "/login?error=login"


def test_oauth_redirect_uses_fixed_origin_and_pkce(client, monkeypatch):
    from urllib.parse import parse_qs, urlsplit

    from authlib.integrations.starlette_client import StarletteOAuth2App

    async def metadata(self):
        return {"authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth"}

    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-secret")
    monkeypatch.setattr(StarletteOAuth2App, "load_server_metadata", metadata)
    response = client.get("/auth/login/google", follow_redirects=False)
    params = parse_qs(urlsplit(response.headers["location"]).query)
    assert params["redirect_uri"] == ["http://localhost:8080/auth/callback/google"]
    assert params["code_challenge_method"] == ["S256"]
    assert params["state"] and params["nonce"]


def test_application_does_not_serve_private_files(policy, monkeypatch):
    from app.server import app

    client = TestClient(app, base_url="http://localhost:8080")
    sign_in(client, monkeypatch)
    for path in (
        "/.env",
        "/app/server.py",
        "/config/auth.json",
        "/knowledge/manual/MANUAL_SCB.pdf",
        "/data/ancine/example.parquet",
        "/.git/config",
    ):
        assert client.get(path).status_code == 404
    assert client.get("/").status_code == 200
    assert client.get("/css/auth.css").status_code == 200
