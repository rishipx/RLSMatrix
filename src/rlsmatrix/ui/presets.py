"""Bundled example presets for the web application."""

from __future__ import annotations

from pathlib import Path

from rlsmatrix.examples import DIRECTORY as EXAMPLES_DIR

# Label -> (example folder, suite file). Every folder contains schema.sql.
PRESETS: dict[str, tuple[str, str]] = {
    "Tenant isolation, improved suite": ("tenant_isolation", "suite.yaml"),
    "Tenant isolation, first-draft suite": (
        "tenant_isolation",
        "suite_first_draft.yaml",
    ),
    "Org projects": ("org_projects", "suite.yaml"),
    "Support tickets": ("support_tickets", "suite.yaml"),
    "Shared notes, first draft (try all operators)": (
        "shared_notes",
        "suite_first_draft.yaml",
    ),
    "Shared notes, improved suite": ("shared_notes", "suite.yaml"),
    "Table owner with FORCE RLS (try all operators)": (
        "owner_force_rls",
        "suite.yaml",
    ),
    "Table owner, no owner actor (try all operators)": (
        "owner_force_rls",
        "suite_no_owner.yaml",
    ),
}
DEFAULT_PRESET = next(iter(PRESETS))


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Could not load example file: {path.name}") from exc


def load_preset(label: str) -> tuple[str, str]:
    """Return the schema SQL and suite YAML for a preset."""
    folder, suite = PRESETS[label]
    return _read(EXAMPLES_DIR / folder / "schema.sql"), _read(
        EXAMPLES_DIR / folder / suite
    )
