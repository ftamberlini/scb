import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.routers.chat import ChatQuestion, router
from app.server import health


def test_health_reports_loading_before_lifespan_initialization():
    response = health()
    assert response.status_code == 503
    assert json.loads(response.body) == {"status": "starting", "error": None}


def test_chat_request_validation_is_enforced_by_router():
    with pytest.raises(ValidationError):
        ChatQuestion(question="")
    assert {route.path for route in router.routes} == {"/api/chat/models", "/api/chat/query"}


def test_stylesheet_is_served_from_the_expected_path():
    stylesheet = Path("css/styles.css")
    assert stylesheet.is_file()
    assert ":root" in stylesheet.read_text()
