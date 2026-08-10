import pytest

from tests.postgres_test_utils import (
    PostgresIntegrationSafetyError,
    load_postgres_test_config,
    postgres_skip_reason,
)


def test_postgres_integration_requires_url_and_separate_opt_in():
    assert "not configured" in postgres_skip_reason({})
    assert "disabled" in postgres_skip_reason({
        "TEST_POSTGRES_DATABASE_URL": "postgresql://user:secret@localhost/daybreak_test"
    })
    assert postgres_skip_reason({
        "TEST_POSTGRES_DATABASE_URL": "postgresql://user:secret@localhost/daybreak_test",
        "ALLOW_POSTGRES_INTEGRATION_TESTS": "1",
    }) is None


def test_postgres_integration_refuses_unmarked_or_production_looking_target():
    base = {
        "TEST_POSTGRES_DATABASE_URL": "postgresql://user:secret@db.example/daybreak",
        "ALLOW_POSTGRES_INTEGRATION_TESTS": "1",
    }
    with pytest.raises(PostgresIntegrationSafetyError, match="refusing"):
        load_postgres_test_config(base)

    production = dict(base)
    production["TEST_POSTGRES_DATABASE_URL"] = (
        "postgresql://user:secret@prod.example/daybreak_test"
    )
    with pytest.raises(PostgresIntegrationSafetyError, match="refusing"):
        load_postgres_test_config(production)


def test_postgres_integration_never_accepts_runtime_database_identity():
    url = "postgresql://test_user:test_password@localhost:5544/daybreak_test"
    with pytest.raises(PostgresIntegrationSafetyError, match="matches DATABASE_URL"):
        load_postgres_test_config({
            "TEST_POSTGRES_DATABASE_URL": url,
            "DATABASE_URL": "postgresql://runtime:other-secret@localhost:5544/daybreak_test",
            "ALLOW_POSTGRES_INTEGRATION_TESTS": "1",
            "ALLOW_UNMARKED_POSTGRES_TEST_DATABASE": "1",
        })


def test_sanitized_identity_never_contains_credentials():
    config = load_postgres_test_config({
        "TEST_POSTGRES_DATABASE_URL": (
            "postgresql://private-user:private-password@localhost:5433/daybreak_test"
        ),
        "ALLOW_POSTGRES_INTEGRATION_TESTS": "1",
    })
    assert config.identity.sanitized == "localhost:5433/daybreak_test"
    assert "private" not in config.identity.sanitized
