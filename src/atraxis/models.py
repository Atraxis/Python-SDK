"""Immutable public models and transfer builders."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
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


def _integer(data: Mapping[str, Any], name: str, *, minimum: int = 0) -> int:
    value = data.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


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
class WarehouseItem:
    warehouse_item_id: int
    item_id: int
    name: str
    quantity: int
    durability: int
    max_durability: int
    transfer_restricted: bool

    @classmethod
    def from_dict(cls, value: object) -> WarehouseItem:
        data = _mapping(value, "warehouse item")
        return cls(
            warehouse_item_id=_identifier(data.get("warehouse_item_id"), "warehouse_item_id"),
            item_id=_identifier(data.get("item_id"), "item_id"),
            name=_text(data, "name"),
            quantity=_integer(data, "quantity", minimum=1),
            durability=_integer(data, "durability"),
            max_durability=_integer(data, "max_durability"),
            transfer_restricted=_boolean(data, "transfer_restricted"),
        )


@dataclass(frozen=True, slots=True)
class WarehousePage:
    is_open: bool
    slots_used: int
    slots_total: int
    items: tuple[WarehouseItem, ...]
    next_cursor: str | None = None

    @classmethod
    def from_dict(cls, value: object) -> WarehousePage:
        data = _mapping(value, "warehouse")
        return cls(
            is_open=_boolean(data, "is_open"),
            slots_used=_integer(data, "slots_used"),
            slots_total=_integer(data, "slots_total"),
            items=tuple(
                WarehouseItem.from_dict(item) for item in _items(data.get("items"), "items")
            ),
            next_cursor=_optional_text(data, "next_cursor"),
        )


@dataclass(frozen=True, slots=True)
class Currency:
    code: str
    name: str
    transferable: bool
    max_supply: int
    total_supply: int
    treasury_balance: int

    @classmethod
    def from_dict(cls, value: object) -> Currency:
        data = _mapping(value, "currency")
        return cls(
            code=_text(data, "code"),
            name=_text(data, "name"),
            transferable=_boolean(data, "transferable"),
            max_supply=_amount(data, "max_supply", minimum=1),
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
        if kind not in {"game_item", "credits", "echos", "guild_currency"}:
            raise ValueError("unknown activity asset type")
        return cls(
            type=kind,
            item_id=_identifier(data["item_id"], "item_id") if "item_id" in data else None,
            warehouse_item_id=(
                _identifier(data["warehouse_item_id"], "warehouse_item_id")
                if "warehouse_item_id" in data
                else None
            ),
            currency_code=_optional_text(data, "currency_code"),
        )


@dataclass(frozen=True, slots=True)
class ActivityEvent:
    event_id: str
    occurred_at: datetime
    operation_id: str
    kind: str
    source: str
    direction: str
    from_party: ActivityParty
    to_party: ActivityParty
    asset: ActivityAsset
    gross: int
    fee: int
    net: int
    balance_before: int | None
    balance_after: int | None
    leg_index: int

    @classmethod
    def from_dict(cls, value: object) -> ActivityEvent:
        data = _mapping(value, "activity")
        occurred_at = datetime.fromisoformat(_text(data, "occurred_at").replace("Z", "+00:00"))
        return cls(
            event_id=_text(data, "event_id"),
            occurred_at=occurred_at,
            operation_id=_text(data, "operation_id"),
            kind=_text(data, "kind"),
            source=_text(data, "source"),
            direction=_text(data, "direction"),
            from_party=ActivityParty.from_dict(data.get("from")),
            to_party=ActivityParty.from_dict(data.get("to")),
            asset=ActivityAsset.from_dict(data.get("asset")),
            gross=_amount(data, "gross", minimum=1),
            fee=_amount(data, "fee"),
            net=_amount(data, "net", minimum=1),
            balance_before=_amount(data, "balance_before") if "balance_before" in data else None,
            balance_after=_amount(data, "balance_after") if "balance_after" in data else None,
            leg_index=_integer(data, "leg_index"),
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
