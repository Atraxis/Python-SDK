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
    "ActivityPage": {"available_since", "items", "next_cursor"},
    "Currency": {
        "code",
        "name",
        "total_supply",
        "transferable",
        "treasury_balance",
    },
    "CurrencyUpdate": {"name", "transferable"},
    "GameItemAsset": {"type", "warehouse_item_id"},
    "GuildCurrencyAsset": {"code", "type"},
    "PlayerBalances": {"balances", "player_id"},
    "Problem": {"detail", "request_id", "status", "title", "type"},
    "Transfer": {"amount", "asset", "from", "to"},
    "TransferResult": {"operation_id", "transfers"},
    "Warehouse": {"items", "next_cursor", "slots_total", "slots_used"},
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
    frozenset({"currency_code", "type"}),
    frozenset({"item_id", "type", "warehouse_item_id"}),
    frozenset({"items"}),
    frozenset({"player_id", "type"}),
    frozenset({"transfers"}),
    frozenset({"type"}),
}
EXPECTED_DOC_FIELDS = {
    "eyebrow",
    "guides",
    "introduction",
    "notes",
    "subtitle",
    "title",
    "tools",
}
EXPECTED_GUIDE_IDS = (
    "warehouse-refill",
    "warehouse-delivery",
    "guild-currencies",
    "safe-retries",
)
EXPECTED_TOOL_LINKS = {
    "python-sdk": "https://github.com/Atraxis/Python-SDK",
    "mcp": (
        "https://github.com/Atraxis/Python-SDK"
        "#подключение-к-codex-и-claude-code"
    ),
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


def validate_activity_asset(schemas: Mapping[str, Any]) -> None:
    schema = require_mapping(schemas.get("ActivityAsset"), "ActivityAsset")
    variants = require_list(schema.get("oneOf"), "ActivityAsset.oneOf")
    expected = {
        "game_item": ({"type", "item_id", "warehouse_item_id"}, {"type", "item_id"}),
        "credits": ({"type"}, {"type"}),
        "echos": ({"type"}, {"type"}),
        "guild_currency": ({"type", "currency_code"}, {"type", "currency_code"}),
    }
    for index, value in enumerate(variants):
        variant = require_mapping(value, f"ActivityAsset.oneOf[{index}]")
        properties = require_mapping(variant.get("properties"), "ActivityAsset.properties")
        type_schema = require_mapping(properties.get("type"), "ActivityAsset.type")
        kind = type_schema.get("const")
        required = set(require_list(variant.get("required"), "ActivityAsset.required"))
        if not isinstance(kind, str) or expected.pop(kind, None) != (set(properties), required):
            raise ValueError("ActivityAsset variants do not match the reviewed contract")
    if expected:
        raise ValueError("ActivityAsset variants do not match the reviewed contract")


def require_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def require_list(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array")
    return value


def validate_documentation(spec: Mapping[str, Any]) -> None:
    docs = require_mapping(spec.get("x-atraxis-docs"), "x-atraxis-docs")
    if set(docs) != EXPECTED_DOC_FIELDS:
        raise ValueError("documentation fields do not match the reviewed contract")
    for field in ("eyebrow", "title", "subtitle"):
        require_string(docs.get(field), f"x-atraxis-docs.{field}")
    for field in ("introduction", "notes"):
        values = require_list(docs.get(field), f"x-atraxis-docs.{field}")
        if not values:
            raise ValueError(f"x-atraxis-docs.{field} must not be empty")
        for index, value in enumerate(values):
            require_string(value, f"x-atraxis-docs.{field}[{index}]")

    guides = require_mapping(docs.get("guides"), "x-atraxis-docs.guides")
    if set(guides) != {"title", "items"}:
        raise ValueError("documentation guide fields do not match the reviewed contract")
    require_string(guides.get("title"), "x-atraxis-docs.guides.title")
    guide_items = require_list(guides.get("items"), "x-atraxis-docs.guides.items")
    if len(guide_items) != len(EXPECTED_GUIDE_IDS):
        raise ValueError("documentation guides do not match the reviewed contract")
    for index, (value, expected_id) in enumerate(
        zip(guide_items, EXPECTED_GUIDE_IDS, strict=True)
    ):
        guide = require_mapping(value, f"guide {index}")
        if set(guide) != {"id", "title", "description"}:
            raise ValueError("documentation guide fields do not match the reviewed contract")
        if guide.get("id") != expected_id:
            raise ValueError("documentation guides do not match the reviewed contract")
        require_string(guide.get("title"), f"guide {index}.title")
        require_string(guide.get("description"), f"guide {index}.description")

    tools = require_mapping(docs.get("tools"), "x-atraxis-docs.tools")
    if set(tools) != {"title", "description", "items"}:
        raise ValueError("documentation tool fields do not match the reviewed contract")
    require_string(tools.get("title"), "x-atraxis-docs.tools.title")
    require_string(tools.get("description"), "x-atraxis-docs.tools.description")
    tool_items = require_list(tools.get("items"), "x-atraxis-docs.tools.items")
    if len(tool_items) != len(EXPECTED_TOOL_LINKS):
        raise ValueError("documentation tools do not match the reviewed contract")
    for index, (value, (expected_id, expected_href)) in enumerate(
        zip(tool_items, EXPECTED_TOOL_LINKS.items(), strict=True)
    ):
        tool = require_mapping(value, f"tool {index}")
        if set(tool) != {
            "id",
            "label",
            "title",
            "description",
            "command",
            "href",
            "link_label",
        }:
            raise ValueError("documentation tool fields do not match the reviewed contract")
        if tool.get("id") != expected_id or tool.get("href") != expected_href:
            raise ValueError("documentation tools do not match the reviewed contract")
        for field in ("label", "title", "description", "command", "link_label"):
            require_string(tool.get(field), f"tool {index}.{field}")


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
    validate_documentation(spec)
    schemas = component_schemas(spec)
    if set(schemas) != EXPECTED_SCHEMAS:
        raise ValueError("component schemas do not match the reviewed public contract")
    for name, fields in EXPECTED_NAMED_SCHEMA_FIELDS.items():
        if schema_properties(schemas, name) != fields:
            raise ValueError("schema fields do not match the reviewed public contract")
    validate_activity_asset(schemas)
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
