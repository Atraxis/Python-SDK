"""Local stdio MCP server backed exclusively by AsyncAtraxisClient."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from datetime import datetime
from importlib.resources import files
from typing import Any, cast

from .client import AsyncAtraxisClient
from .errors import AtraxisError
from .models import CurrencyTransfer, ItemTransfer, TransferInput


def _jsonable(value: object) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable(asdict(cast(Any, value)))
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, tuple | list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _jsonable_dict(value: object) -> dict[str, object]:
    result = _jsonable(value)
    if not isinstance(result, dict):
        raise RuntimeError("Atraxis model could not be serialized")
    return cast(dict[str, object], result)


def _mapping_or_empty(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _resolve_contract_refs(root: Mapping[str, Any], value: object) -> object:
    if isinstance(value, Mapping):
        reference = value.get("$ref")
        if isinstance(reference, str):
            if not reference.startswith("#/"):
                raise RuntimeError("Packaged Atraxis contract contains an external reference")
            resolved: object = root
            for segment in reference[2:].split("/"):
                key = segment.replace("~1", "/").replace("~0", "~")
                if not isinstance(resolved, Mapping) or key not in resolved:
                    raise RuntimeError("Packaged Atraxis contract contains an invalid reference")
                resolved = resolved[key]
            return _resolve_contract_refs(root, resolved)
        return {str(key): _resolve_contract_refs(root, child) for key, child in value.items()}
    if isinstance(value, list):
        return [_resolve_contract_refs(root, child) for child in value]
    return value


def _safe_failure(error: Exception) -> dict[str, object]:
    if isinstance(error, AtraxisError):
        return {"error": {"message": str(error)}}
    if isinstance(error, ValueError):
        return {"error": {"message": str(error)}}
    return {"error": {"message": "Atraxis request failed"}}


def _contract() -> Mapping[str, Any]:
    path = files("atraxis._contract").joinpath("guild-commerce-v1.json")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise RuntimeError("Packaged Atraxis contract is invalid")
    return value


def _client(token: str, base_url: str | None) -> AsyncAtraxisClient:
    return AsyncAtraxisClient(token, base_url=base_url)


def _parse_transfer(value: object) -> TransferInput:
    if not isinstance(value, Mapping):
        raise ValueError("Each transfer must be an object")
    kind = value.get("type")
    amount = value.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise ValueError("Transfer amount must be an integer")
    if kind == "item":
        warehouse_item_id = value.get("warehouse_item_id")
        player_id = value.get("player_id")
        if isinstance(warehouse_item_id, bool) or not isinstance(warehouse_item_id, int):
            raise ValueError("warehouse_item_id must be an integer")
        if isinstance(player_id, bool) or not isinstance(player_id, int):
            raise ValueError("player_id must be an integer")
        return ItemTransfer(warehouse_item_id=warehouse_item_id, player_id=player_id, amount=amount)
    code = value.get("code")
    if kind not in {"issue", "retire", "to_player", "from_player", "between_players"}:
        raise ValueError("Unknown transfer type")
    if not isinstance(code, str):
        raise ValueError("Currency code must be a string")
    if kind == "issue":
        return CurrencyTransfer.issue(code, amount=amount)
    if kind == "retire":
        return CurrencyTransfer.retire(code, amount=amount)
    player_id = value.get("player_id")
    if kind in {"to_player", "from_player"}:
        if isinstance(player_id, bool) or not isinstance(player_id, int):
            raise ValueError("player_id must be an integer")
        if kind == "to_player":
            return CurrencyTransfer.to_player(code, player_id=player_id, amount=amount)
        return CurrencyTransfer.from_player(code, player_id=player_id, amount=amount)
    from_player_id = value.get("from_player_id")
    to_player_id = value.get("to_player_id")
    if isinstance(from_player_id, bool) or not isinstance(from_player_id, int):
        raise ValueError("from_player_id must be an integer")
    if isinstance(to_player_id, bool) or not isinstance(to_player_id, int):
        raise ValueError("to_player_id must be an integer")
    return CurrencyTransfer.between_players(
        code,
        from_player_id=from_player_id,
        to_player_id=to_player_id,
        amount=amount,
    )


def build_server(*, token: str | None, base_url: str | None, allow_writes: bool) -> object:
    try:
        from mcp.server import MCPServer
        from mcp.types import ToolAnnotations
    except ImportError as exc:  # pragma: no cover - exercised in installation smoke
        raise RuntimeError('Install MCP support with: pip install "atraxis-sdk[mcp]"') from exc

    mcp = MCPServer(
        "atraxis",
        title="Atraxis API",
        description="Safe local tools for the public Atraxis guild API.",
        instructions=(
            "Use read tools to inspect one bounded API page at a time. "
            "Never request, repeat, or expose ATRAXIS_API_TOKEN. "
            "Writes exist only when the operator started the server with --allow-writes."
        ),
    )
    readonly = ToolAnnotations(read_only_hint=True, idempotent_hint=True)
    mutation = ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=True)

    @mcp.tool(annotations=readonly)
    def atraxis_api_overview() -> dict[str, object]:
        """Return public API metadata and the six operation identifiers. No token is required."""
        spec = _contract()
        info = _mapping_or_empty(spec.get("info"))
        paths = _mapping_or_empty(spec.get("paths"))
        operations = []
        for path, path_item in paths.items():
            if not isinstance(path_item, Mapping):
                continue
            for method in ("get", "put", "post"):
                operation = path_item.get(method)
                if isinstance(operation, Mapping):
                    operations.append(
                        {
                            "method": method.upper(),
                            "path": path,
                            "operation_id": operation.get("operationId"),
                            "summary": operation.get("summary"),
                        }
                    )
        return {
            "title": info.get("title"),
            "version": info.get("version"),
            "description": info.get("description"),
            "operations": operations,
        }

    @mcp.tool(annotations=readonly)
    def atraxis_api_endpoint(operation_id: str) -> dict[str, object]:
        """Return the curated public OpenAPI fragment for one operation identifier."""
        spec = _contract()
        paths = _mapping_or_empty(spec.get("paths"))
        for path, path_item in paths.items():
            if not isinstance(path_item, Mapping):
                continue
            for method in ("get", "put", "post"):
                operation = path_item.get(method)
                if isinstance(operation, Mapping) and operation.get("operationId") == operation_id:
                    return {
                        "method": method.upper(),
                        "path": path,
                        "operation": _resolve_contract_refs(spec, operation),
                    }
        return {"error": {"message": "Unknown Atraxis operation_id"}}

    if token:

        @mcp.tool(annotations=readonly)
        async def atraxis_get_warehouse(
            page_size: int = 50, cursor: str | None = None
        ) -> dict[str, object]:
            """Read one bounded page of the authenticated guild warehouse."""
            try:
                async with _client(token, base_url) as client:
                    return _jsonable_dict(
                        await client.get_warehouse(page_size=page_size, cursor=cursor)
                    )
            except Exception as error:
                return _safe_failure(error)

        @mcp.tool(annotations=readonly)
        async def atraxis_list_currencies() -> dict[str, object]:
            """Read the authenticated guild's internal currencies."""
            try:
                async with _client(token, base_url) as client:
                    return {"items": _jsonable(await client.list_currencies())}
            except Exception as error:
                return _safe_failure(error)

        @mcp.tool(annotations=readonly)
        async def atraxis_get_balances(player_id: int) -> dict[str, object]:
            """Read one player's balances in the authenticated guild's currencies."""
            try:
                async with _client(token, base_url) as client:
                    return _jsonable_dict(await client.get_balances(player_id))
            except Exception as error:
                return _safe_failure(error)

        @mcp.tool(annotations=readonly)
        async def atraxis_get_activity(
            page_size: int = 50, cursor: str | None = None
        ) -> dict[str, object]:
            """Read one bounded page of public guild value-movement activity."""
            try:
                async with _client(token, base_url) as client:
                    return _jsonable_dict(
                        await client.get_activity(page_size=page_size, cursor=cursor)
                    )
            except Exception as error:
                return _safe_failure(error)

        if allow_writes:

            @mcp.tool(annotations=mutation)
            async def atraxis_upsert_currency(
                code: str,
                name: str,
                transferable: bool,
                max_supply: int,
            ) -> dict[str, object]:
                """Create or replace one guild currency configuration."""
                try:
                    async with _client(token, base_url) as client:
                        return _jsonable_dict(
                            await client.upsert_currency(
                                code,
                                name=name,
                                transferable=transferable,
                                max_supply=max_supply,
                            )
                        )
                except Exception as error:
                    return _safe_failure(error)

            @mcp.tool(annotations=mutation)
            async def atraxis_transfer(
                transfers: Sequence[dict[str, object]],
                idempotency_key: str,
            ) -> dict[str, object]:
                """Apply 1-10 transfers atomically.

                An explicit stable idempotency key is required.
                """
                try:
                    if not idempotency_key.strip():
                        raise ValueError("idempotency_key is required")
                    parsed = [_parse_transfer(item) for item in transfers]
                    async with _client(token, base_url) as client:
                        return _jsonable_dict(
                            await client.transfer(parsed, idempotency_key=idempotency_key)
                        )
                except Exception as error:
                    return _safe_failure(error)

    return mcp


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Atraxis MCP server over stdio")
    parser.add_argument(
        "--allow-writes",
        action="store_true",
        help="Register currency and transfer mutation tools",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("ATRAXIS_API_BASE_URL"),
        help="Override the Atraxis API base URL (token still comes only from the environment)",
    )
    args = parser.parse_args()
    server = build_server(
        token=os.getenv("ATRAXIS_API_TOKEN"),
        base_url=args.base_url,
        allow_writes=args.allow_writes,
    )
    asyncio.run(server.run_stdio_async())  # type: ignore[attr-defined]


if __name__ == "__main__":
    main()
