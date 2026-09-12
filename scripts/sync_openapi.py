#!/usr/bin/env python3
"""Validate and store the curated Atraxis public OpenAPI snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import yaml

EXPECTED_OPERATIONS = {
    ("/warehouse", "get"),
    ("/currencies", "get"),
    ("/currencies/{code}", "put"),
    ("/balances/{player_id}", "get"),
    ("/transfers", "post"),
    ("/activity", "get"),
}
EXPECTED_SCHEMAS = {
    "Activity",
    "ActivityAsset",
    "ActivityPage",
    "ActivityParty",
    "Amount",
    "Currency",
    "CurrencyCode",
    "CurrencyUpdate",
    "DecimalID",
    "GameItemAsset",
    "GuildCurrencyAsset",
    "NonNegativeAmount",
    "Party",
    "PlayerBalances",
    "Problem",
    "Transfer",
    "TransferResult",
    "Warehouse",
    "WarehouseItem",
}
EXPECTED_NAMED_SCHEMA_FIELDS = {
    "Activity": {
        "event_id",
        "occurred_at",
        "operation_id",
        "kind",
        "source",
        "direction",
        "from",
        "to",
        "asset",
        "gross",
        "fee",
        "net",
        "balance_before",
        "balance_after",
        "leg_index",
    },
    "ActivityAsset": {"currency_code", "item_id", "type", "warehouse_item_id"},
    "ActivityPage": {"available_since", "items", "next_cursor"},
    "Currency": {
        "code",
        "max_supply",
        "name",
        "total_supply",
        "transferable",
        "treasury_balance",
    },
    "CurrencyUpdate": {"max_supply", "name", "transferable"},
    "GameItemAsset": {"type", "warehouse_item_id"},
    "GuildCurrencyAsset": {"code", "type"},
    "PlayerBalances": {"balances", "player_id"},
    "Problem": {"detail", "request_id", "status", "title", "type"},
    "Transfer": {"amount", "asset", "from", "to"},
    "TransferResult": {"operation_id", "transfers"},
    "Warehouse": {"is_open", "items", "next_cursor", "slots_total", "slots_used"},
    "WarehouseItem": {
        "durability",
        "item_id",
        "max_durability",
        "name",
        "quantity",
        "transfer_restricted",
        "warehouse_item_id",
    },
}
EXPECTED_PROPERTY_SETS = {
    frozenset(fields) for fields in EXPECTED_NAMED_SCHEMA_FIELDS.values()
} | {
    frozenset({"amount", "asset", "from", "index", "to"}),
    frozenset({"balance", "code"}),
    frozenset({"items"}),
    frozenset({"player_id", "type"}),
    frozenset({"transfers"}),
    frozenset({"type"}),
}


def schema_property_sets(value: object) -> set[frozenset[str]]:
    found: set[frozenset[str]] = set()
    if isinstance(value, Mapping):
        properties = value.get("properties")
        if isinstance(properties, Mapping):
            found.add(frozenset(str(name) for name in properties))
        for child in value.values():
            found.update(schema_property_sets(child))
    elif isinstance(value, list):
        for child in value:
            found.update(schema_property_sets(child))
    return found


def load_source(source: str) -> object:
    parsed = urlparse(source)
    if parsed.scheme in {"http", "https"}:
        request = Request(source, headers={"Accept": "application/json"})
        with urlopen(request, timeout=20) as response:
            payload = response.read()
    else:
        payload = Path(source).read_bytes()
    try:
        return json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return yaml.safe_load(payload)


def require_mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def component_schemas(spec: Mapping[str, Any]) -> Mapping[str, Any]:
    components = require_mapping(spec.get("components"), "components")
    return require_mapping(components.get("schemas"), "components.schemas")


def schema_properties(schemas: Mapping[str, Any], name: str) -> set[str]:
    schema = require_mapping(schemas.get(name), name)
    properties = require_mapping(schema.get("properties"), f"{name}.properties")
    return set(properties)


def validate(spec_value: object) -> Mapping[str, Any]:
    spec = require_mapping(spec_value, "OpenAPI")
    if spec.get("openapi") != "3.1.0":
        raise ValueError("only OpenAPI 3.1.0 is accepted")
    servers = spec.get("servers")
    if not isinstance(servers, list) or len(servers) != 1:
        raise ValueError("exactly one relative server is required")
    server = require_mapping(servers[0], "server")
    if server.get("url") != "/api/external/v1":
        raise ValueError("server must be /api/external/v1")

    paths = require_mapping(spec.get("paths"), "paths")
    operations = {
        (path, method)
        for path, path_item_value in paths.items()
        for method in require_mapping(path_item_value, path)
        if method in {"get", "put", "post", "patch", "delete"}
    }
    if operations != EXPECTED_OPERATIONS:
        raise ValueError(
            f"unexpected public operations: {sorted(operations ^ EXPECTED_OPERATIONS)}"
        )
    schemas = component_schemas(spec)
    if set(schemas) != EXPECTED_SCHEMAS:
        raise ValueError("component schemas do not match the reviewed public contract")
    for name, fields in EXPECTED_NAMED_SCHEMA_FIELDS.items():
        if schema_properties(schemas, name) != fields:
            raise ValueError("schema fields do not match the reviewed public contract")
    if not schema_property_sets(spec).issubset(EXPECTED_PROPERTY_SETS):
        raise ValueError("schema fields do not match the reviewed public contract")
    return spec


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "source", help="Public OpenAPI JSON URL or an explicit local YAML/JSON path"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("src/atraxis/_contract/guild-commerce-v1.json"),
    )
    args = parser.parse_args()

    spec = validate(load_source(args.source))
    normalized = json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    digest = hashlib.sha256(normalized.encode()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(normalized, encoding="utf-8")
    args.output.with_suffix(".sha256").write_text(f"{digest}\n", encoding="ascii")
    print(f"stored {args.output} sha256={digest}")


if __name__ == "__main__":
    main()
