from datetime import date

from app.database import (
    cinema_week,
    cinema_year,
    classify_registration,
    execute_with_timeout,
    first_thursday,
)


def test_registration_classification():
    assert classify_registration("B123") == "CPB"
    assert classify_registration("E123") == "ROE"
    assert classify_registration("G123") == "OUTRO"


def test_cinema_calendar_boundary():
    assert first_thursday(2025) == date(2025, 1, 2)
    assert cinema_year(date(2025, 1, 1)) == 2024
    assert cinema_year(date(2025, 1, 2)) == 2025
    assert cinema_week(date(2025, 1, 2)) == 1
    assert cinema_week(date(2025, 1, 8)) == 1
    assert cinema_week(date(2025, 1, 9)) == 2


def test_query_execution_helper_returns_duckdb_cursor():
    import duckdb

    connection = duckdb.connect(":memory:")
    try:
        assert execute_with_timeout(connection, "SELECT ?", [42]).fetchone() == (42,)
    finally:
        connection.close()
