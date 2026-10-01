from __future__ import annotations

import pytest

from atraxis import WarehouseItemCondition, WarehouseItemInstance


@pytest.mark.parametrize(
    ("payload", "attribute"),
    [
        (
            {
                "kind": "gather_tool",
                "gathering": {
                    "max_resource_tier": 4,
                    "speed_bonus_percent": 25,
                    "rarity_bonus_percent": 15,
                    "base_speed_bonus_percent": 20,
                    "base_rarity_bonus_percent": 10,
                    "stats_modifier_percent": 25,
                },
            },
            "gathering",
        ),
        (
            {
                "kind": "fishing_rod",
                "fishing_rod": {
                    "speed_bonus_percent": 16,
                    "rarity_bonus_percent": 14,
                    "base_speed_bonus_percent": 10,
                    "base_rarity_bonus_percent": 10,
                    "stats_modifier_percent": 4,
                    "double_catch_chance_percent": 12,
                },
            },
            "fishing_rod",
        ),
        (
            {
                "kind": "shield",
                "shield_abilities": [
                    {"slot": 1, "ability_id": "heal", "ability_name": "Лечение", "level": 7}
                ],
            },
            "shield_abilities",
        ),
        (
            {
                "kind": "fish",
                "fish": {
                    "species_key": "test_fish",
                    "weight_grams": 1234,
                    "freshness_percent": 66.67,
                    "source_kind": "spot",
                    "was_school_catch": False,
                },
            },
            "fish",
        ),
        ({"kind": "artifact", "artifact_enabled": True}, "artifact_enabled"),
        (
            {"kind": "journal", "journal": {"state": "filling", "fill_percent": 43.25}},
            "journal",
        ),
        ({"kind": "other"}, "kind"),
    ],
)
def test_instance_parser_covers_every_public_kind(
    payload: dict[str, object], attribute: str
) -> None:
    instance = WarehouseItemInstance.from_dict(payload)
    assert getattr(instance, attribute) is not None


@pytest.mark.parametrize(
    "payload",
    [
        {"current": 101, "maximum": 100, "unit": "percent"},
        {"current": 0, "maximum": 0, "unit": "points"},
        {"current": 1, "maximum": 100, "unit": "unknown"},
    ],
)
def test_condition_parser_rejects_ambiguous_or_impossible_values(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        WarehouseItemCondition.from_dict(payload)


def test_condition_parser_preserves_units_and_fractional_percent() -> None:
    condition = WarehouseItemCondition.from_dict(
        {"current": 98.76, "maximum": 100, "unit": "percent"}
    )
    assert condition.current == 98.76
    assert condition.maximum == 100
    assert condition.unit == "percent"


def test_instance_parser_enforces_bounded_percentages() -> None:
    with pytest.raises(ValueError):
        WarehouseItemInstance.from_dict(
            {
                "kind": "fishing_rod",
                "fishing_rod": {
                    "speed_bonus_percent": 16,
                    "rarity_bonus_percent": 14,
                    "base_speed_bonus_percent": 10,
                    "base_rarity_bonus_percent": 10,
                    "stats_modifier_percent": 4,
                    "double_catch_chance_percent": 101,
                },
            }
        )
