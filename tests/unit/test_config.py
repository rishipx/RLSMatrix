import pytest

from rlsmatrix.config import Settings


def test_rejects_external_database_host() -> None:
    settings = Settings(database_host="db.example.com", database_password="test-only")
    with pytest.raises(RuntimeError, match="dedicated Docker Compose service"):
        settings.validate()


def test_rejects_nonstandard_sandbox_port() -> None:
    settings = Settings(database_port=6432, database_password="test-only")
    with pytest.raises(RuntimeError, match="port must be 5432"):
        settings.validate()


def test_accepts_sandbox_defaults() -> None:
    Settings().validate()


def test_environment_does_not_supply_a_default_database_password(monkeypatch) -> None:
    monkeypatch.delenv("RLSMATRIX_DB_PASSWORD", raising=False)
    settings = Settings.from_environment()
    assert settings.database_password == ""


def test_workers_setting_is_bounded() -> None:
    Settings(workers=16).validate()
    for bad in (0, 17):
        with pytest.raises(ValueError, match="WORKERS"):
            Settings(workers=bad).validate()


def test_non_integer_environment_values_are_reported_by_name(monkeypatch) -> None:
    monkeypatch.setenv("RLSMATRIX_WORKERS", "many")
    with pytest.raises(ValueError, match="RLSMATRIX_WORKERS must be an integer"):
        Settings.from_environment()
