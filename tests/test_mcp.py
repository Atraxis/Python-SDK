from __future__ import annotations

import pytest
from mcp.client import Client

from atraxis.mcp_server import build_server


async def tool_names(*, token: str | None, allow_writes: bool) -> set[str]:
    server = build_server(
        token=token, base_url="https://example.test/api/external/v1", allow_writes=allow_writes
    )
    async with Client(server) as client:  # type: ignore[arg-type]
        result = await client.list_tools()
    return {tool.name for tool in result.tools}


@pytest.mark.asyncio
async def test_mcp_without_token_exposes_only_public_contract_tools() -> None:
    names = await tool_names(token=None, allow_writes=True)
    assert names == {"atraxis_api_overview", "atraxis_api_endpoint"}


@pytest.mark.asyncio
async def test_mcp_read_tools_require_token_and_writes_require_explicit_flag() -> None:
    read_only = await tool_names(token="agk_example.redacted", allow_writes=False)
    assert "atraxis_get_warehouse" in read_only
    assert "atraxis_get_activity" in read_only
    assert "atraxis_upsert_currency" not in read_only
    assert "atraxis_transfer" not in read_only

    writable = await tool_names(token="agk_example.redacted", allow_writes=True)
    assert {"atraxis_upsert_currency", "atraxis_transfer"}.issubset(writable)


@pytest.mark.asyncio
async def test_mcp_contract_tool_runs_through_real_client_session() -> None:
    server = build_server(token=None, base_url=None, allow_writes=False)
    async with Client(server) as client:  # type: ignore[arg-type]
        result = await client.call_tool("atraxis_api_overview", {})

        endpoint = await client.call_tool(
            "atraxis_api_endpoint", {"operation_id": "getGuildWarehouse"}
        )

    assert result.is_error is False
    assert result.structured_content is not None
    assert result.structured_content["version"] == "1.0.0"

    assert endpoint.is_error is False
    assert endpoint.structured_content is not None
    operation = endpoint.structured_content["operation"]
    assert "$ref" not in str(operation)
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["properties"]
