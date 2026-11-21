"""Settings read from the environment, with validated limits."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

SANDBOX_HOST = "postgres"
SANDBOX_PORT = 5432
SANDBOX_MAINTENANCE_DB = "postgres"
MIN_WORKERS = 1
MAX_WORKERS = 16


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}.") from exc


def _require_range(name: str, value: int, low: int, high: int) -> None:
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}.")


@dataclass(frozen=True, slots=True)
class Settings:
    database_host: str = SANDBOX_HOST
    database_port: int = SANDBOX_PORT
    database_name: str = SANDBOX_MAINTENANCE_DB
    database_user: str = "postgres"
    database_password: str = ""
    connect_timeout_seconds: int = 5
    statement_timeout_ms: int = 5_000
    lock_timeout_ms: int = 1_500
    max_bootstrap_bytes: int = 1_000_000
    max_manifest_bytes: int = 512_000
    max_probe_sql_bytes: int = 100_000
    max_result_rows: int = 10_000
    max_mutations: int = 500
    workers: int = 4

    @classmethod
    def from_environment(cls) -> Settings:
        settings = cls(
            database_host=os.getenv("RLSMATRIX_DB_HOST", SANDBOX_HOST),
            database_port=_env_int("RLSMATRIX_DB_PORT", SANDBOX_PORT),
            database_name=os.getenv("RLSMATRIX_DB_NAME", SANDBOX_MAINTENANCE_DB),
            database_user=os.getenv("RLSMATRIX_DB_USER", "postgres"),
            database_password=os.getenv("RLSMATRIX_DB_PASSWORD", ""),
            connect_timeout_seconds=_env_int("RLSMATRIX_CONNECT_TIMEOUT", 5),
            statement_timeout_ms=_env_int("RLSMATRIX_STATEMENT_TIMEOUT_MS", 5_000),
            lock_timeout_ms=_env_int("RLSMATRIX_LOCK_TIMEOUT_MS", 1_500),
            max_bootstrap_bytes=_env_int("RLSMATRIX_MAX_BOOTSTRAP_BYTES", 1_000_000),
            max_manifest_bytes=_env_int("RLSMATRIX_MAX_MANIFEST_BYTES", 512_000),
            max_probe_sql_bytes=_env_int("RLSMATRIX_MAX_PROBE_SQL_BYTES", 100_000),
            max_result_rows=_env_int("RLSMATRIX_MAX_RESULT_ROWS", 10_000),
            max_mutations=_env_int("RLSMATRIX_MAX_MUTATIONS", 500),
            workers=_env_int("RLSMATRIX_WORKERS", 4),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.database_host != SANDBOX_HOST:
            raise RuntimeError(
                "RLSMatrix only connects to its dedicated Docker Compose service "
                f"named '{SANDBOX_HOST}'. External database hosts are not supported."
            )
        if self.database_port != SANDBOX_PORT:
            raise RuntimeError(f"The sandbox database port must be {SANDBOX_PORT}.")
        if self.database_name != SANDBOX_MAINTENANCE_DB:
            raise RuntimeError(
                f"The sandbox maintenance database must be '{SANDBOX_MAINTENANCE_DB}'."
            )
        if not self.database_user:
            raise RuntimeError("Sandbox database user must not be empty.")
        _require_range("RLSMATRIX_CONNECT_TIMEOUT", self.connect_timeout_seconds, 1, 30)
        _require_range(
            "RLSMATRIX_STATEMENT_TIMEOUT_MS", self.statement_timeout_ms, 250, 60_000
        )
        _require_range("RLSMATRIX_LOCK_TIMEOUT_MS", self.lock_timeout_ms, 100, 30_000)
        _require_range(
            "RLSMATRIX_MAX_BOOTSTRAP_BYTES", self.max_bootstrap_bytes, 1, 10_000_000
        )
        _require_range(
            "RLSMATRIX_MAX_MANIFEST_BYTES", self.max_manifest_bytes, 1, 2_000_000
        )
        _require_range(
            "RLSMATRIX_MAX_PROBE_SQL_BYTES", self.max_probe_sql_bytes, 1, 1_000_000
        )
        _require_range("RLSMATRIX_MAX_RESULT_ROWS", self.max_result_rows, 1, 100_000)
        _require_range("RLSMATRIX_MAX_MUTATIONS", self.max_mutations, 1, 2_000)
        _require_range("RLSMATRIX_WORKERS", self.workers, MIN_WORKERS, MAX_WORKERS)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_environment()
