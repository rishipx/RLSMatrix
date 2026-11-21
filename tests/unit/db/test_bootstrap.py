import pytest

from rlsmatrix.db.bootstrap import _created_role_name, validate_bootstrap


def test_created_role_name_detects_create_role_variants() -> None:
    assert _created_role_name("CREATE ROLE anon NOLOGIN") == "anon"
    assert _created_role_name("create user bob") == "bob"
    assert _created_role_name("-- note\nCREATE ROLE svc NOLOGIN BYPASSRLS;") == "svc"


def test_created_role_name_ignores_other_statements() -> None:
    assert _created_role_name("CREATE TABLE role_assignments (id int)") is None
    assert _created_role_name("ALTER ROLE anon NOLOGIN") is None
    assert _created_role_name("this is not sql about a role") is None


def test_validate_bootstrap_rejects_empty_scripts() -> None:
    for script in ("", "   \n"):
        with pytest.raises(ValueError, match="empty"):
            validate_bootstrap(script)
