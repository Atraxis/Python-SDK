"""Typed clients and models for the public Atraxis API."""

from ._version import PACKAGE_VERSION
from .client import AsyncAtraxisClient, AtraxisClient
from .errors import AtraxisAPIError, AtraxisError, AtraxisResponseError, AtraxisTransportError
from .models import (
    ActivityEvent,
    ActivityPage,
    Balance,
    Currency,
    CurrencyTransfer,
    ItemTransfer,
    PlayerBalances,
    TransferResult,
    WarehouseCombatStats,
    WarehouseFishDetails,
    WarehouseFishingRodStats,
    WarehouseGatheringStats,
    WarehouseItem,
    WarehouseItemCondition,
    WarehouseItemInstance,
    WarehouseJournalDetails,
    WarehousePage,
    WarehousePassiveSkill,
    WarehouseShieldAbility,
)

__all__ = [
    "ActivityEvent",
    "ActivityPage",
    "AsyncAtraxisClient",
    "AtraxisAPIError",
    "AtraxisClient",
    "AtraxisError",
    "AtraxisResponseError",
    "AtraxisTransportError",
    "Balance",
    "Currency",
    "CurrencyTransfer",
    "ItemTransfer",
    "PlayerBalances",
    "TransferResult",
    "WarehouseCombatStats",
    "WarehouseFishDetails",
    "WarehouseFishingRodStats",
    "WarehouseGatheringStats",
    "WarehouseItem",
    "WarehouseItemCondition",
    "WarehouseItemInstance",
    "WarehouseJournalDetails",
    "WarehousePage",
    "WarehousePassiveSkill",
    "WarehouseShieldAbility",
]

__version__ = PACKAGE_VERSION
