from __future__ import annotations

from datetime import timedelta

import pytest

from atraxis.models import ActivityPage, WarehouseFishDetails
from atraxis.public_models import PublicEventPage


@pytest.mark.parametrize("digits", range(10))
@pytest.mark.parametrize(
    ("zone", "offset"),
    [
        ("Z", timedelta()),
        ("+03:00", timedelta(hours=3)),
        ("-03:30", -timedelta(hours=3, minutes=30)),
    ],
)
def test_public_dates_accept_go_fractional_precision(
    digits: int, zone: str, offset: timedelta
) -> None:
    fraction = "123456789"[:digits]
    value = "2026-10-30T16:32:22" + ("." + fraction if fraction else "") + zone
    page = PublicEventPage.from_dict({"items": [], "server_time": value})

    assert page.server_time.microsecond == int(fraction.ljust(6, "0")[:6])
    assert page.server_time.utcoffset() == offset


def test_legacy_dates_accept_nanoseconds_without_rounding() -> None:
    value = "2026-10-30T16:32:22.999999999Z"
    page = ActivityPage.from_dict({"items": [], "available_since": value})
    fish = WarehouseFishDetails.from_dict(
        {
            "species_key": "test_fish",
            "weight_grams": 100,
            "was_school_catch": False,
            "caught_at": value,
            "expires_at": value,
        }
    )

    assert page.available_since is not None
    assert fish.caught_at == fish.expires_at == page.available_since
    assert page.available_since.second == 22
    assert page.available_since.microsecond == 999999


@pytest.mark.parametrize("value", ["2026-10-30", "2026-10-30T16:32:22.123456789", "invalid"])
def test_public_dates_still_require_valid_timezone(value: str) -> None:
    with pytest.raises(ValueError):
        PublicEventPage.from_dict({"items": [], "server_time": value})
