"""Pydantic models for actors, probes and test suites."""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Actor(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    role: str = Field(min_length=1, max_length=63, pattern=r"^[a-zA-Z0-9_$-]+$")
    sub: str | None = Field(default=None, max_length=256)
    claims: dict[str, Any] = Field(default_factory=dict, max_length=64)


class Probe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    actor: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=240)
    sql: str = Field(min_length=1, max_length=100_000)
    expected_rows: list[list[Any]] = Field(default_factory=list, max_length=10_000)
    expect_error: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def error_expectation_is_exclusive(self) -> Probe:
        if self.expect_error is not None and self.expected_rows:
            raise ValueError("Use either expected_rows or expect_error, not both")
        return self


class TestSuite(BaseModel):
    __test__: ClassVar[bool] = False  # not a pytest class
    model_config = ConfigDict(extra="forbid")

    name: str = Field(default="RLS test suite", min_length=1, max_length=120)
    actors: list[Actor] = Field(min_length=1, max_length=32)
    probes: list[Probe] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_references(self) -> TestSuite:
        actor_ids = [actor.id for actor in self.actors]
        probe_ids = [probe.id for probe in self.probes]
        if len(actor_ids) != len(set(actor_ids)):
            raise ValueError("Actor IDs must be unique")
        if len(probe_ids) != len(set(probe_ids)):
            raise ValueError("Probe IDs must be unique")
        unknown = sorted({probe.actor for probe in self.probes} - set(actor_ids))
        if unknown:
            raise ValueError(f"Probes reference unknown actors: {', '.join(unknown)}")
        return self
