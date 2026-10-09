"""Typed clients and models for the public Atraxis API."""

from ._version import PACKAGE_VERSION
from .client import AsyncAtraxisClient, AtraxisClient
from .errors import AtraxisAPIError, AtraxisError, AtraxisResponseError, AtraxisTransportError
from .models import (
    ActivityEvent,
    ActivityPage,
    ActivityWarehouseItem,
    Balance,
    Currency,
    CurrencyTransfer,
    ItemTransfer,
    PlayerBalances,
    PlayerIdentities,
    PlayerIdentity,
    TransferResult,
    Warehouse,
    WarehouseCombatStats,
    WarehouseFishDetails,
    WarehouseFishingRodStats,
    WarehouseGatheringStats,
    WarehouseItem,
    WarehouseItemCondition,
    WarehouseItemInstance,
    WarehouseJournalDetails,
    WarehousePassiveSkill,
    WarehouseShieldAbility,
)

__all__ = [
    "ActivityEvent",
    "ActivityPage",
    "ActivityWarehouseItem",
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
    "PlayerIdentities",
    "PlayerIdentity",
    "TransferResult",
    "Warehouse",
    "WarehouseCombatStats",
    "WarehouseFishDetails",
    "WarehouseFishingRodStats",
    "WarehouseGatheringStats",
    "WarehouseItem",
    "WarehouseItemCondition",
    "WarehouseItemInstance",
    "WarehouseJournalDetails",
    "WarehousePassiveSkill",
    "WarehouseShieldAbility",
]

__version__ = PACKAGE_VERSION
