"""Organization allowlist read from a private configuration file."""

import json
import os
import re
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class PolicyError(ValueError):
    pass


def domain(value):
    if not isinstance(value, str):
        raise PolicyError("Domínio inválido.")
    try:
        value = value.strip().lower().encode("idna").decode("ascii")
    except UnicodeError as error:
        raise PolicyError("Domínio inválido.") from error
    if len(value) > 253 or not re.fullmatch(
        r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+", value
    ):
        raise PolicyError("Use domínios completos, sem @, curingas ou URLs.")
    return value


def load_policy():
    try:
        path = Path(os.getenv("AUTH_CONFIG_FILE", str(ROOT / "config/auth.json")))
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or set(data) != {
            "allowed_email_domains",
            "microsoft_tenants",
        }:
            raise PolicyError("Configuração de organizações inválida.")
        if not isinstance(data["allowed_email_domains"], list) or not isinstance(
            data["microsoft_tenants"], dict
        ):
            raise PolicyError("Configuração de organizações inválida.")
        allowed = {domain(d) for d in data["allowed_email_domains"]}
        tenants = {domain(d): str(uuid.UUID(t)) for d, t in data["microsoft_tenants"].items()}
        if not tenants.keys() <= allowed:
            raise PolicyError("Todo domínio Microsoft deve estar na lista de domínios permitidos.")
        # Organizational access does not accept the personal Microsoft account tenant.
        if "9188040d-6c67-4c5b-b112-36a304b66dad" in tenants.values():
            raise PolicyError("Configure tenants organizacionais Microsoft.")
        return allowed, tenants
    except (OSError, ValueError, TypeError, AttributeError) as error:
        raise PolicyError("Não foi possível carregar a configuração de acesso.") from error


def is_allowed(user, policy):
    allowed, tenants = policy
    email = user.get("email", "")
    if not isinstance(email, str) or len(email) > 320 or email.count("@") != 1:
        return False
    local, email_domain = email.rsplit("@", 1)
    if not local or any(c.isspace() for c in email):
        return False
    try:
        email_domain = domain(email_domain)
    except PolicyError:
        return False
    if email_domain not in allowed:
        return False
    if user.get("provider") == "google":
        # Workspace membership must come from hd, not merely an email suffix.
        hd = user.get("hd")
        return (
            user.get("email_verified") is True
            and isinstance(hd, str)
            and hd.lower() == email_domain
        )
    if user.get("provider") == "microsoft":
        # Authorize a member of the trusted tenant; email is an additional filter.
        return (
            bool(user.get("oid"))
            and user.get("tid") == tenants.get(email_domain)
            and user.get("acct") in (0, "0")
        )
    return False
