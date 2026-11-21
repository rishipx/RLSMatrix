import pytest

from rlsmatrix.examples import DIRECTORY
from rlsmatrix.ui.presets import DEFAULT_PRESET, EXAMPLES_DIR, PRESETS, load_preset


def test_examples_are_located_inside_the_package() -> None:
    assert EXAMPLES_DIR == DIRECTORY
    assert (DIRECTORY / "__init__.py").is_file()


@pytest.mark.parametrize("label", list(PRESETS))
def test_every_preset_loads(label: str) -> None:
    schema, manifest = load_preset(label)
    assert "CREATE" in schema.upper()
    assert "probes:" in manifest


def test_the_default_preset_is_the_first() -> None:
    assert next(iter(PRESETS)) == DEFAULT_PRESET
