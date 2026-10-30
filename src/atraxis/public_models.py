"""Immutable models for the anonymous public event and announcement API."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from .models import (
    _boolean,
    _integer,
    _items,
    _mapping,
    _optional_integer,
    _optional_number,
    _optional_text,
    _parse_datetime,
    _string,
    _text,
)


def _date(data: Mapping[str, Any], name: str, *, nullable: bool = False) -> datetime | None:
    if name not in data:
        raise ValueError(f"{name} is required")
    value = data[name]
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an RFC 3339 timestamp")
    result = _parse_datetime(value)
    if result.tzinfo is None:
        raise ValueError(f"{name} must contain a timezone")
    return result


def _required_date(data: Mapping[str, Any], name: str) -> datetime:
    value = _date(data, name)
    assert value is not None
    return value


def _decimal(value: object, name: str, *, zero: bool = False) -> str:
    if (
        not isinstance(value, str)
        or not value.isascii()
        or not value.isdecimal()
        or str(int(value)) != value
        or (not zero and int(value) == 0)
    ):
        raise ValueError(f"{name} must be a canonical decimal string")
    return value


def _uuid(value: object, name: str) -> str:
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise ValueError(f"{name} must be a canonical UUID")
    return value


@dataclass(frozen=True)
class PublicPlayerMention:
    player_id: str
    name: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PublicPlayerMention:
        return cls(_decimal(data.get("player_id"), "player_id"), _text(data, "name"))


@dataclass(frozen=True)
class PublicEventLocation:
    approximate: bool
    name: str | None = None
    x: int | None = None
    y: int | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PublicEventLocation:
        return cls(
            _boolean(data, "approximate"),
            _optional_text(data, "name"),
            _optional_integer(data, "x"),
            _optional_integer(data, "y"),
        )


@dataclass(frozen=True)
class PublicEventLot:
    id: str
    title: str
    quantity: int
    ends_at: datetime | None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PublicEventLot:
        return cls(
            _decimal(data.get("id"), "id"),
            _text(data, "title"),
            _integer(data, "quantity"),
            _date(data, "ends_at", nullable=True),
        )


@dataclass(frozen=True)
class PublicEventDetails:
    variant: str | None = None
    boss_current_hp: str | None = None
    boss_max_hp: str | None = None
    research_multiplier: float | None = None
    format: str | None = None
    level: int | None = None
    location: PublicEventLocation | None = None
    target: PublicPlayerMention | None = None
    kills_required: int | None = None
    reward_per_kill: str | None = None
    lots: tuple[PublicEventLot, ...] = ()
    guilds: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PublicEventDetails:
        def decimal(name: str) -> str | None:
            return _decimal(data[name], name, zero=True) if name in data else None

        guilds = _items(data.get("guilds", []), "guilds")
        if any(not isinstance(name, str) or not name for name in guilds):
            raise ValueError("guilds must contain non-empty names")
        return cls(
            variant=_optional_text(data, "variant"),
            boss_current_hp=decimal("boss_current_hp"),
            boss_max_hp=decimal("boss_max_hp"),
            research_multiplier=_optional_number(data, "research_multiplier"),
            format=_optional_text(data, "format"),
            level=_optional_integer(data, "level", minimum=1),
            location=PublicEventLocation.from_dict(_mapping(data["location"], "location"))
            if "location" in data
            else None,
            target=PublicPlayerMention.from_dict(_mapping(data["target"], "target"))
            if "target" in data
            else None,
            kills_required=_optional_integer(data, "kills_required", minimum=1),
            reward_per_kill=decimal("reward_per_kill"),
            lots=tuple(
                PublicEventLot.from_dict(_mapping(item, "lot"))
                for item in _items(data.get("lots", []), "lots")
            ),
            guilds=tuple(str(name) for name in guilds),
        )


@dataclass(frozen=True)
class PublicEvent:
    id: str
    kind: str
    title: str
    description: str
    status: str
    phase: str
    announced_at: datetime
    starts_at: datetime | None
    ends_at: datetime | None
    updated_at: datetime
    details: PublicEventDetails

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PublicEvent:
        status = _text(data, "status")
        if status not in {"scheduled", "active", "finalizing"}:
            raise ValueError("invalid public event status")
        return cls(
            _uuid(data.get("id"), "id"),
            _text(data, "kind"),
            _text(data, "title"),
            _string(data, "description"),
            status,
            _text(data, "phase"),
            _required_date(data, "announced_at"),
            _date(data, "starts_at", nullable=True),
            _date(data, "ends_at", nullable=True),
            _required_date(data, "updated_at"),
            PublicEventDetails.from_dict(_mapping(data.get("details"), "details")),
        )


@dataclass(frozen=True)
class PublicEventPage:
    items: tuple[PublicEvent, ...]
    server_time: datetime
    next_cursor: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PublicEventPage:
        return cls(
            tuple(
                PublicEvent.from_dict(_mapping(item, "event"))
                for item in _items(data.get("items"), "items")
            ),
            _required_date(data, "server_time"),
            _optional_text(data, "next_cursor"),
        )


@dataclass(frozen=True)
class PublicAnnouncement:
    id: str
    kind: str
    text: str
    mentions: tuple[PublicPlayerMention, ...]
    occurred_at: datetime
    published_at: datetime
    event_id: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PublicAnnouncement:
        return cls(
            _decimal(data.get("id"), "id"),
            _text(data, "kind"),
            _text(data, "text"),
            tuple(
                PublicPlayerMention.from_dict(_mapping(item, "mention"))
                for item in _items(data.get("mentions"), "mentions")
            ),
            _required_date(data, "occurred_at"),
            _required_date(data, "published_at"),
            _uuid(data["event_id"], "event_id") if "event_id" in data else None,
        )


@dataclass(frozen=True)
class PublicAnnouncementPage:
    items: tuple[PublicAnnouncement, ...]
    checkpoint: str
    available_since: datetime
    next_cursor: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PublicAnnouncementPage:
        return cls(
            tuple(
                PublicAnnouncement.from_dict(_mapping(item, "announcement"))
                for item in _items(data.get("items"), "items")
            ),
            _decimal(data.get("checkpoint"), "checkpoint", zero=True),
            _required_date(data, "available_since"),
            _optional_text(data, "next_cursor"),
        )
