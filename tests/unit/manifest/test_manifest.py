import pytest
import yaml
from pydantic import ValidationError

from rlsmatrix.examples import DIRECTORY as EXAMPLES
from rlsmatrix.manifest import load_test_suite


def test_demo_manifest_is_valid() -> None:
    source = (EXAMPLES / "tenant_isolation" / "suite.yaml").read_text(encoding="utf-8")
    suite = load_test_suite(source)

    assert suite.name == "Two-tenant document isolation"
    assert {actor.id for actor in suite.actors} == {
        "anonymous",
        "alice",
        "bob",
        "service",
    }
    assert len(suite.probes) == 6


def test_rejects_duplicate_yaml_keys() -> None:
    source = """
name: first
name: second
actors:
  - id: reader
    role: authenticated
probes:
  - id: read
    actor: reader
    sql: SELECT 1;
"""
    with pytest.raises(yaml.YAMLError, match="duplicate key"):
        load_test_suite(source)


def test_rejects_unknown_actor_reference() -> None:
    source = """
name: bad manifest
actors:
  - id: alice
    role: authenticated
probes:
  - id: probe
    actor: bob
    sql: SELECT 1;
"""
    with pytest.raises(ValidationError, match="unknown actors"):
        load_test_suite(source)


def test_rejects_empty_manifest() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        load_test_suite("  \n")
