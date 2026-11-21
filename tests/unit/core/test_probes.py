from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

from rlsmatrix.core.probes import normalize


def test_normalize_makes_database_values_comparable_with_yaml() -> None:
    assert normalize(Decimal("1.5")) == 1.5
    assert normalize(Decimal("1")) == 1
    assert normalize(UUID(int=1)) == "00000000-0000-0000-0000-000000000001"
    assert normalize(date(2026, 1, 2)) == "2026-01-02"
    assert normalize(datetime(2026, 1, 2, 3, 4)) == "2026-01-02T03:04:00"
    assert normalize(time(3, 4)) == "03:04:00"
    assert normalize(timedelta(minutes=1)) == 60.0


def test_normalize_handles_binary_and_nested_values() -> None:
    assert normalize(b"\x01\xff") == "01ff"
    assert normalize(memoryview(b"\x01")) == "01"
    assert normalize({1: (Decimal("2"), [UUID(int=0)])}) == {
        "1": [2.0, ["00000000-0000-0000-0000-000000000000"]]
    }
