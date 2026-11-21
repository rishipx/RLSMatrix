"""Integration tests need the Docker Compose PostgreSQL sandbox.

They are skipped automatically when RLSMATRIX_DB_PASSWORD is unset or the
sandbox host is unreachable, so `pytest` stays green on a laptop without Docker.
"""

import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def _require_sandbox() -> None:
    if not os.getenv("RLSMATRIX_DB_PASSWORD"):
        pytest.skip("RLSMATRIX_DB_PASSWORD is not set")
    from rlsmatrix.db.sandbox import list_roles

    try:
        list_roles()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"PostgreSQL sandbox unavailable: {type(exc).__name__}")
