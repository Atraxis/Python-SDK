"""Immutable public models and transfer builders."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from math import isfinite
from typing import Any

MAX_AMOUNT = 9_000_000_000_000_000
CURRENCY_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{0,15}$")


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _items(value: object, name: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array")
    return value


def _text(data: Mapping[str, Any], name: str) -> str:
    value = data.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _optional_text(data: Mapping[str, Any], name: str) -> str | None:
    value = data.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _string(data: Mapping[str, Any], name: str) -> str:
    value = data.get(name)
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    return value


def _integer(data: Mapping[str, Any], name: str, *, minimum: int = 0) -> int:
    value = data.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _optional_integer(
    data: Mapping[str, Any], name: str, *, minimum: int | None = None
) -> int | None:
    value = data.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return int(value)


def _number(
    data: Mapping[str, Any],
    name: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    value = data.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    parsed = float(value)
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{name} must be a number >= {minimum}")
    if maximum is not None and parsed > maximum:
        raise ValueError(f"{name} must be a number <= {maximum}")
    return parsed


def _optional_number(
    data: Mapping[str, Any],
    name: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float | None:
    if data.get(name) is None:
        return None
    return _number(data, name, minimum=minimum, maximum=maximum)


def _amount(data: Mapping[str, Any], name: str, *, minimum: int = 0) -> int:
    value = data.get(name)
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
        raise ValueError(f"{name} must be a decimal string")
    if value != "0" and value.startswith("0"):
        raise ValueError(f"{name} must be canonical")
    parsed = int(value)
    if parsed < minimum or parsed > MAX_AMOUNT:
        raise ValueError(f"{name} is outside the public range")
    return parsed


def _boolean(data: Mapping[str, Any], name: str) -> bool:
    value = data.get(name)
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _optional_boolean(data: Mapping[str, Any], name: str) -> bool | None:
    if data.get(name) is None:
        return None
    return _boolean(data, name)


def _identifier(value: object, name: str) -> int:
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
        raise ValueError(f"{name} must be a decimal string")
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def _validate_positive_amount(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_AMOUNT:
        raise ValueError(f"amount must be between 1 and {MAX_AMOUNT}")
    return value


def _validate_player_id(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("player_id must be a positive integer")
    return value


@dataclass(frozen=True, slots=True)
class WarehouseItemCondition:
    current: float
    maximum: float
    unit: str

    @classmethod
    def from_dict(cls, value: object) -> WarehouseItemCondition:
        data = _mapping(value, "warehouse item condition")
        unit = _text(data, "unit")
        if unit not in {"percent", "points"}:
            raise ValueError("unknown warehouse item condition unit")
        current = _number(data, "current", minimum=0)
        maximum = _number(data, "maximum", minimum=0)
        if maximum <= 0 or current > maximum:
            raise ValueError("warehouse item condition is outside the public range")
        return cls(current=current, maximum=maximum, unit=unit)


@dataclass(frozen=True, slots=True)
class WarehouseCombatStats:
    attack: int
    strength: int
    dexterity: int
    intelligence: int
    armor: int
    stamina: int
    base_attack: int
    base_strength: int
    base_dexterity: int
    base_intelligence: int
    base_armor: int
    base_stamina: int

    @classmethod
    def from_dict(cls, value: object) -> WarehouseCombatStats:
        data = _mapping(value, "warehouse combat stats")
        return cls(**{name: _integer(data, name) for name in cls.__dataclass_fields__})


@dataclass(frozen=True, slots=True)
class WarehousePassiveSkill:
    slot: int
    skill_id: int
    name: str
    base_modifier_percent: float

    @classmethod
    def from_dict(cls, value: object) -> WarehousePassiveSkill:
        data = _mapping(value, "warehouse passive skill")
        slot = _integer(data, "slot", minimum=1)
        if slot > 2:
            raise ValueError("passive skill slot must be 1 or 2")
        return cls(
            slot=slot,
            skill_id=_identifier(data.get("skill_id"), "skill_id"),
            name=_text(data, "name"),
            base_modifier_percent=_number(data, "base_modifier_percent"),
        )


@dataclass(frozen=True, slots=True)
class WarehouseGatheringStats:
    max_resource_tier: int
    speed_bonus_percent: float
    rarity_bonus_percent: float
    base_speed_bonus_percent: float
    base_rarity_bonus_percent: float
    stats_modifier_percent: float

    @classmethod
    def from_dict(cls, value: object) -> WarehouseGatheringStats:
        data = _mapping(value, "warehouse gathering stats")
        return cls(
            max_resource_tier=_integer(data, "max_resource_tier", minimum=1),
            speed_bonus_percent=_number(data, "speed_bonus_percent"),
            rarity_bonus_percent=_number(data, "rarity_bonus_percent"),
            base_speed_bonus_percent=_number(data, "base_speed_bonus_percent"),
            base_rarity_bonus_percent=_number(data, "base_rarity_bonus_percent"),
            stats_modifier_percent=_number(data, "stats_modifier_percent"),
        )


@dataclass(frozen=True, slots=True)
class WarehouseFishingRodStats:
    speed_bonus_percent: float
    rarity_bonus_percent: float
    base_speed_bonus_percent: float
    base_rarity_bonus_percent: float
    stats_modifier_percent: float
    double_catch_chance_percent: float

    @classmethod
    def from_dict(cls, value: object) -> WarehouseFishingRodStats:
        data = _mapping(value, "warehouse fishing rod stats")
        return cls(
            speed_bonus_percent=_number(data, "speed_bonus_percent"),
            rarity_bonus_percent=_number(data, "rarity_bonus_percent"),
            base_speed_bonus_percent=_number(data, "base_speed_bonus_percent"),
            base_rarity_bonus_percent=_number(data, "base_rarity_bonus_percent"),
            stats_modifier_percent=_number(data, "stats_modifier_percent"),
            double_catch_chance_percent=_number(
                data, "double_catch_chance_percent", minimum=0, maximum=100
            ),
        )


@dataclass(frozen=True, slots=True)
class WarehouseShieldAbility:
    slot: int
    level: int
    ability_id: str | None = None
    ability_name: str | None = None

    @classmethod
    def from_dict(cls, value: object) -> WarehouseShieldAbility:
        data = _mapping(value, "warehouse shield ability")
        slot = _integer(data, "slot", minimum=1)
        level = _integer(data, "level")
        if slot > 2 or level > 10:
            raise ValueError("shield ability is outside the public range")
        return cls(
            slot=slot,
            level=level,
            ability_id=_optional_text(data, "ability_id"),
            ability_name=_optional_text(data, "ability_name"),
        )


@dataclass(frozen=True, slots=True)
class WarehouseFishDetails:
    species_key: str
    weight_grams: int
    was_school_catch: bool
    caught_at: datetime | None = None
    expires_at: datetime | None = None
    freshness_percent: float | None = None
    region: str | None = None
    biome: str | None = None
    source_kind: str | None = None

    @classmethod
    def from_dict(cls, value: object) -> WarehouseFishDetails:
        data = _mapping(value, "warehouse fish details")
        caught_at = _optional_text(data, "caught_at")
        expires_at = _optional_text(data, "expires_at")
        source_kind = _optional_text(data, "source_kind")
        if source_kind not in {None, "spot", "school"}:
            raise ValueError("unknown fishing source kind")
        return cls(
            species_key=_string(data, "species_key"),
            weight_grams=_integer(data, "weight_grams"),
            was_school_catch=_boolean(data, "was_school_catch"),
            caught_at=datetime.fromisoformat(caught_at.replace("Z", "+00:00"))
            if caught_at
            else None,
            expires_at=datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if expires_at
            else None,
            freshness_percent=_optional_number(data, "freshness_percent", minimum=0, maximum=100),
            region=_optional_text(data, "region"),
            biome=_optional_text(data, "biome"),
            source_kind=source_kind,
        )


@dataclass(frozen=True, slots=True)
class WarehouseJournalDetails:
    state: str
    fill_percent: float

    @classmethod
    def from_dict(cls, value: object) -> WarehouseJournalDetails:
        data = _mapping(value, "warehouse journal details")
        state = _text(data, "state")
        if state not in {"empty", "filling", "filled", "unknown"}:
            raise ValueError("unknown journal state")
        return cls(
            state=state,
            fill_percent=_number(data, "fill_percent", minimum=0, maximum=100),
        )


@dataclass(frozen=True, slots=True)
class WarehouseItemInstance:
    kind: str
    level: int | None = None
    quality: str | None = None
    base_upgrade_chance_percent: float | None = None
    upgrade_chance_percent: float | None = None
    upgrade_level: int | None = None
    stats_modifier_percent: float | None = None
    power_percent: float | None = None
    awakened: bool | None = None
    awakening_failures: int | None = None
    combat_stats: WarehouseCombatStats | None = None
    passive_skills: tuple[WarehousePassiveSkill, ...] = ()
    gathering: WarehouseGatheringStats | None = None
    fishing_rod: WarehouseFishingRodStats | None = None
    shield_abilities: tuple[WarehouseShieldAbility, ...] = ()
    fish: WarehouseFishDetails | None = None
    artifact_enabled: bool | None = None
    journal: WarehouseJournalDetails | None = None

    @classmethod
    def from_dict(cls, value: object) -> WarehouseItemInstance:
        data = _mapping(value, "warehouse item instance")
        kind = _text(data, "kind")
        if kind not in {
            "equipment",
            "gather_tool",
            "fishing_rod",
            "shield",
            "fish",
            "artifact",
            "journal",
            "other",
        }:
            raise ValueError("unknown warehouse item instance kind")
        quality = _optional_text(data, "quality")
        if quality not in {None, "I", "II", "III"}:
            raise ValueError("unknown warehouse item quality")
        passive_skills = data.get("passive_skills", [])
        shield_abilities = data.get("shield_abilities", [])
        return cls(
            kind=kind,
            level=_optional_integer(data, "level"),
            quality=quality,
            base_upgrade_chance_percent=_optional_number(
                data, "base_upgrade_chance_percent", minimum=0, maximum=100
            ),
            upgrade_chance_percent=_optional_number(
                data, "upgrade_chance_percent", minimum=0, maximum=100
            ),
            upgrade_level=_optional_integer(data, "upgrade_level", minimum=0),
            stats_modifier_percent=_optional_number(data, "stats_modifier_percent"),
            power_percent=_optional_number(data, "power_percent"),
            awakened=_optional_boolean(data, "awakened"),
            awakening_failures=_optional_integer(data, "awakening_failures", minimum=0),
            combat_stats=(
                WarehouseCombatStats.from_dict(data["combat_stats"])
                if "combat_stats" in data
                else None
            ),
            passive_skills=tuple(
                WarehousePassiveSkill.from_dict(item)
                for item in _items(passive_skills, "passive_skills")
            ),
            gathering=(
                WarehouseGatheringStats.from_dict(data["gathering"])
                if "gathering" in data
                else None
            ),
            fishing_rod=(
                WarehouseFishingRodStats.from_dict(data["fishing_rod"])
                if "fishing_rod" in data
                else None
            ),
            shield_abilities=tuple(
                WarehouseShieldAbility.from_dict(item)
                for item in _items(shield_abilities, "shield_abilities")
            ),
            fish=WarehouseFishDetails.from_dict(data["fish"]) if "fish" in data else None,
            artifact_enabled=_optional_boolean(data, "artifact_enabled"),
            journal=(
                WarehouseJournalDetails.from_dict(data["journal"]) if "journal" in data else None
            ),
        )


@dataclass(frozen=True, slots=True)
class WarehouseItem:
    warehouse_item_id: int
    item_id: int
    name: str
    quantity: int
    durability: int
    max_durability: int
    transfer_restricted: bool
    item_type: str | None = None
    set_type: str | None = None
    rarity: str | None = None
    tier: int | None = None
    is_unique: bool = False
    condition: WarehouseItemCondition | None = None
    instance: WarehouseItemInstance | None = None

    @classmethod
    def from_dict(cls, value: object) -> WarehouseItem:
        data = _mapping(value, "warehouse item")
        instance = WarehouseItemInstance.from_dict(data["instance"]) if "instance" in data else None
        is_unique = _boolean(data, "is_unique") if "is_unique" in data else instance is not None
        if instance is not None and not is_unique:
            raise ValueError("warehouse item instance requires is_unique=true")
        return cls(
            warehouse_item_id=_identifier(data.get("warehouse_item_id"), "warehouse_item_id"),
            item_id=_identifier(data.get("item_id"), "item_id"),
            name=_text(data, "name"),
            quantity=_integer(data, "quantity", minimum=1),
            durability=_integer(data, "durability"),
            max_durability=_integer(data, "max_durability"),
            transfer_restricted=_boolean(data, "transfer_restricted"),
            item_type=_text(data, "item_type") if "item_type" in data else None,
            set_type=_optional_text(data, "set_type"),
            rarity=_string(data, "rarity") if "rarity" in data else None,
            tier=_optional_integer(data, "tier", minimum=0),
            is_unique=is_unique,
            condition=(
                WarehouseItemCondition.from_dict(data["condition"]) if "condition" in data else None
            ),
            instance=instance,
        )


@dataclass(frozen=True, slots=True)
class Warehouse:
    slots_used: int
    slots_total: int
    items: tuple[WarehouseItem, ...]
    activity_checkpoint: str | None = None

    @classmethod
    def from_dict(cls, value: object) -> Warehouse:
        data = _mapping(value, "warehouse")
        return cls(
            slots_used=_integer(data, "slots_used"),
            slots_total=_integer(data, "slots_total"),
            items=tuple(
                WarehouseItem.from_dict(item) for item in _items(data.get("items"), "items")
            ),
            activity_checkpoint=_optional_text(data, "activity_checkpoint"),
        )


@dataclass(frozen=True, slots=True)
class Currency:
    code: str
    name: str
    transferable: bool
    total_supply: int
    treasury_balance: int

    @classmethod
    def from_dict(cls, value: object) -> Currency:
        data = _mapping(value, "currency")
        return cls(
            code=_text(data, "code"),
            name=_text(data, "name"),
            transferable=_boolean(data, "transferable"),
            total_supply=_amount(data, "total_supply"),
            treasury_balance=_amount(data, "treasury_balance"),
        )


@dataclass(frozen=True, slots=True)
class Balance:
    code: str
    balance: int

    @classmethod
    def from_dict(cls, value: object) -> Balance:
        data = _mapping(value, "balance")
        return cls(code=_text(data, "code"), balance=_amount(data, "balance"))


@dataclass(frozen=True, slots=True)
class PlayerBalances:
    player_id: int
    balances: tuple[Balance, ...]

    @classmethod
    def from_dict(cls, value: object) -> PlayerBalances:
        data = _mapping(value, "player balances")
        return cls(
            player_id=_identifier(data.get("player_id"), "player_id"),
            balances=tuple(
                Balance.from_dict(item) for item in _items(data.get("balances"), "balances")
            ),
        )


@dataclass(frozen=True, slots=True)
class TransferParty:
    type: str
    player_id: int | None = None

    def to_wire(self) -> dict[str, str]:
        result = {"type": self.type}
        if self.player_id is not None:
            result["player_id"] = str(self.player_id)
        return result

    @classmethod
    def from_dict(cls, value: object) -> TransferParty:
        data = _mapping(value, "party")
        kind = _text(data, "type")
        if kind not in {"guild", "supply", "player"}:
            raise ValueError("unknown party type")
        player_id = data.get("player_id")
        if kind == "player":
            return cls(kind, _identifier(player_id, "player_id"))
        if player_id is not None:
            raise ValueError("non-player party cannot include player_id")
        return cls(kind)


@dataclass(frozen=True, slots=True)
class TransferAsset:
    type: str
    warehouse_item_id: int | None = None
    code: str | None = None

    def to_wire(self) -> dict[str, str]:
        result = {"type": self.type}
        if self.warehouse_item_id is not None:
            result["warehouse_item_id"] = str(self.warehouse_item_id)
        if self.code is not None:
            result["code"] = self.code
        return result

    @classmethod
    def from_dict(cls, value: object) -> TransferAsset:
        data = _mapping(value, "asset")
        kind = _text(data, "type")
        if kind == "game_item":
            return cls(
                kind,
                warehouse_item_id=_identifier(data.get("warehouse_item_id"), "warehouse_item_id"),
            )
        if kind == "guild_currency":
            return cls(kind, code=_text(data, "code"))
        raise ValueError("unknown transfer asset type")


@dataclass(frozen=True, slots=True)
class ItemTransfer:
    warehouse_item_id: int
    player_id: int
    amount: int = 1

    def __post_init__(self) -> None:
        _validate_player_id(self.warehouse_item_id)
        _validate_player_id(self.player_id)
        _validate_positive_amount(self.amount)

    def to_wire(self) -> dict[str, object]:
        return {
            "asset": {"type": "game_item", "warehouse_item_id": str(self.warehouse_item_id)},
            "from": {"type": "guild"},
            "to": {"type": "player", "player_id": str(self.player_id)},
            "amount": str(self.amount),
        }


@dataclass(frozen=True, slots=True)
class CurrencyTransfer:
    code: str
    from_party: TransferParty
    to_party: TransferParty
    amount: int

    def __post_init__(self) -> None:
        if not CURRENCY_CODE_PATTERN.fullmatch(self.code):
            raise ValueError("code must match [A-Z][A-Z0-9_]{0,15}")
        _validate_positive_amount(self.amount)

    @classmethod
    def issue(cls, code: str, *, amount: int) -> CurrencyTransfer:
        return cls(code, TransferParty("supply"), TransferParty("guild"), amount)

    @classmethod
    def retire(cls, code: str, *, amount: int) -> CurrencyTransfer:
        return cls(code, TransferParty("guild"), TransferParty("supply"), amount)

    @classmethod
    def to_player(cls, code: str, *, player_id: int, amount: int) -> CurrencyTransfer:
        return cls(
            code,
            TransferParty("guild"),
            TransferParty("player", _validate_player_id(player_id)),
            amount,
        )

    @classmethod
    def from_player(cls, code: str, *, player_id: int, amount: int) -> CurrencyTransfer:
        return cls(
            code,
            TransferParty("player", _validate_player_id(player_id)),
            TransferParty("guild"),
            amount,
        )

    @classmethod
    def between_players(
        cls,
        code: str,
        *,
        from_player_id: int,
        to_player_id: int,
        amount: int,
    ) -> CurrencyTransfer:
        source = _validate_player_id(from_player_id)
        target = _validate_player_id(to_player_id)
        if source == target:
            raise ValueError("players must be different")
        return cls(code, TransferParty("player", source), TransferParty("player", target), amount)

    def to_wire(self) -> dict[str, object]:
        return {
            "asset": {"type": "guild_currency", "code": self.code},
            "from": self.from_party.to_wire(),
            "to": self.to_party.to_wire(),
            "amount": str(self.amount),
        }


TransferInput = ItemTransfer | CurrencyTransfer


@dataclass(frozen=True, slots=True)
class TransferLeg:
    index: int
    asset: TransferAsset
    from_party: TransferParty
    to_party: TransferParty
    amount: int

    @classmethod
    def from_dict(cls, value: object) -> TransferLeg:
        data = _mapping(value, "transfer")
        return cls(
            index=_integer(data, "index"),
            asset=TransferAsset.from_dict(data.get("asset")),
            from_party=TransferParty.from_dict(data.get("from")),
            to_party=TransferParty.from_dict(data.get("to")),
            amount=_amount(data, "amount", minimum=1),
        )


@dataclass(frozen=True, slots=True)
class TransferResult:
    operation_id: str
    transfers: tuple[TransferLeg, ...]
    idempotency_key: str = field(repr=False)
    request_id: str | None = None
    replayed: bool = False

    @classmethod
    def from_dict(
        cls,
        value: object,
        *,
        idempotency_key: str,
        request_id: str | None,
        replayed: bool,
    ) -> TransferResult:
        data = _mapping(value, "transfer result")
        return cls(
            operation_id=_text(data, "operation_id"),
            transfers=tuple(
                TransferLeg.from_dict(item) for item in _items(data.get("transfers"), "transfers")
            ),
            idempotency_key=idempotency_key,
            request_id=request_id,
            replayed=replayed,
        )


@dataclass(frozen=True, slots=True)
class ActivityParty:
    type: str
    player_id: int | None = None

    @classmethod
    def from_dict(cls, value: object) -> ActivityParty:
        party = TransferParty.from_dict(value)
        return cls(type=party.type, player_id=party.player_id)


@dataclass(frozen=True, slots=True)
class ActivityAsset:
    type: str
    item_id: int | None = None
    warehouse_item_id: int | None = None
    currency_code: str | None = None

    @classmethod
    def from_dict(cls, value: object) -> ActivityAsset:
        data = _mapping(value, "activity asset")
        kind = _text(data, "type")
        if kind == "game_item":
            return cls(
                type=kind,
                item_id=_identifier(data.get("item_id"), "item_id"),
                warehouse_item_id=(
                    _identifier(data["warehouse_item_id"], "warehouse_item_id")
                    if "warehouse_item_id" in data
                    else None
                ),
            )
        if kind == "guild_currency":
            return cls(type=kind, currency_code=_text(data, "currency_code"))
        if kind in {"credits", "echos"}:
            return cls(type=kind)
        raise ValueError("unknown activity asset type")


@dataclass(frozen=True, slots=True)
class ActivityWarehouseItem:
    warehouse_item_id: int
    item_id: int
    name: str
    quantity_before: int
    quantity_after: int
    durability: int
    max_durability: int
    transfer_restricted: bool
    item_type: str | None = None
    set_type: str | None = None
    rarity: str | None = None
    tier: int | None = None
    is_unique: bool = False
    condition: WarehouseItemCondition | None = None
    instance: WarehouseItemInstance | None = None

    @classmethod
    def from_dict(cls, value: object) -> ActivityWarehouseItem:
        data = _mapping(value, "activity warehouse item")
        quantity_before = _amount(data, "quantity_before")
        quantity_after = _amount(data, "quantity_after")
        warehouse_data = dict(data)
        warehouse_data["quantity"] = max(1, quantity_before, quantity_after)
        item = WarehouseItem.from_dict(warehouse_data)
        return cls(
            warehouse_item_id=item.warehouse_item_id,
            item_id=item.item_id,
            name=item.name,
            quantity_before=quantity_before,
            quantity_after=quantity_after,
            durability=item.durability,
            max_durability=item.max_durability,
            transfer_restricted=item.transfer_restricted,
            item_type=item.item_type,
            set_type=item.set_type,
            rarity=item.rarity,
            tier=item.tier,
            is_unique=item.is_unique,
            condition=item.condition,
            instance=item.instance,
        )


@dataclass(frozen=True, slots=True)
class ActivityEvent:
    event_id: str
    occurred_at: datetime
    operation_id: str
    kind: str
    source: str
    from_party: ActivityParty
    to_party: ActivityParty
    asset: ActivityAsset
    gross: int
    fee: int
    net: int
    balance_before: int | None
    balance_after: int | None
    leg_index: int
    deposit_method: str | None = None
    warehouse_item: ActivityWarehouseItem | None = None

    @classmethod
    def from_dict(cls, value: object) -> ActivityEvent:
        data = _mapping(value, "activity")
        occurred_at = datetime.fromisoformat(_text(data, "occurred_at").replace("Z", "+00:00"))
        kind = _text(data, "kind")
        deposit_method = _optional_text(data, "deposit_method")
        if deposit_method not in {None, "guild_deposit", "tagged_transfer"}:
            raise ValueError("unknown warehouse deposit method")
        if kind != "warehouse_deposit" and deposit_method is not None:
            raise ValueError("deposit_method is only valid for warehouse deposits")
        return cls(
            event_id=_text(data, "event_id"),
            occurred_at=occurred_at,
            operation_id=_text(data, "operation_id"),
            kind=kind,
            source=_text(data, "source"),
            from_party=ActivityParty.from_dict(data.get("from")),
            to_party=ActivityParty.from_dict(data.get("to")),
            asset=ActivityAsset.from_dict(data.get("asset")),
            gross=_amount(data, "gross", minimum=1),
            fee=_amount(data, "fee"),
            net=_amount(data, "net", minimum=1),
            balance_before=_amount(data, "balance_before") if "balance_before" in data else None,
            balance_after=_amount(data, "balance_after") if "balance_after" in data else None,
            leg_index=_integer(data, "leg_index"),
            deposit_method=deposit_method,
            warehouse_item=(
                ActivityWarehouseItem.from_dict(data["warehouse_item"])
                if "warehouse_item" in data
                else None
            ),
        )


@dataclass(frozen=True, slots=True)
class ActivityPage:
    items: tuple[ActivityEvent, ...]
    next_cursor: str | None = None
    available_since: datetime | None = None

    @classmethod
    def from_dict(cls, value: object) -> ActivityPage:
        data = _mapping(value, "activity page")
        available = _optional_text(data, "available_since")
        return cls(
            items=tuple(
                ActivityEvent.from_dict(item) for item in _items(data.get("items"), "items")
            ),
            next_cursor=_optional_text(data, "next_cursor"),
            available_since=datetime.fromisoformat(available.replace("Z", "+00:00"))
            if available
            else None,
        )
