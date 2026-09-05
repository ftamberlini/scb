import pytest

from app.chat.sql_validator import SQLValidationError, validate_and_prepare


def test_adds_default_limit_to_read_query():
    assert validate_and_prepare("SELECT * FROM obra") == "SELECT * FROM obra LIMIT 500"


def test_clamps_large_limit():
    assert validate_and_prepare("SELECT * FROM obra LIMIT 9999").endswith("LIMIT 2000")


@pytest.mark.parametrize(
    "query",
    [
        "DELETE FROM obra",
        "SELECT * FROM secret_table",
        "SELECT * FROM read_parquet('/etc/passwd')",
        "SELECT * FROM obra; SELECT * FROM bilheteria",
    ],
)
def test_rejects_unsafe_queries(query):
    with pytest.raises(SQLValidationError):
        validate_and_prepare(query)
