from __future__ import annotations

import httpx
import pytest
from mcp.client import Client

from atraxis import (
    AsyncAtraxisClient,
    AtraxisAPIError,
    AtraxisClient,
    AtraxisResponseError,
)
from atraxis.mcp_server import build_server

DATE = "2026-10-29T12:00:00Z"


def announcement_page(identifier: str = "1", cursor: str | None = None) -> dict[str, object]:
    result: dict[str, object] = {
        "items": [
            {
                "id": identifier,
                "kind": "system",
                "text": "Объявление",
                "mentions": [],
                "occurred_at": DATE,
                "published_at": DATE,
            }
        ],
        "checkpoint": identifier,
        "available_since": DATE,
    }
    if cursor:
        result["next_cursor"] = cursor
    return result


def test_anonymous_client_reads_public_data_and_guild_methods_require_token() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert "authorization" not in request.headers
        return httpx.Response(200, json={"items": [], "server_time": DATE})

    with AtraxisClient(token="", transport=httpx.MockTransport(handle)) as client:
        assert client.get_events().items == ()
        with pytest.raises(ValueError, match="token is required"):
            client.get_warehouse()


def test_public_reads_omit_configured_token_and_page_forward() -> None:
    queries: list[httpx.QueryParams] = []

    def handle(request: httpx.Request) -> httpx.Response:
        assert "authorization" not in request.headers
        queries.append(request.url.params)
        assert request.url.params["after_id"] == "0"
        assert request.url.params["order"] == "asc"
        payload = (
            announcement_page("2")
            if "cursor" in request.url.params
            else announcement_page("1", "next")
        )
        return httpx.Response(200, json=payload)

    with AtraxisClient("secret", transport=httpx.MockTransport(handle)) as client:
        assert [item.id for item in client.iter_new_announcements(after_id="0")] == ["1", "2"]
    assert len(queries) == 2
    assert queries[1]["cursor"] == "next"


def test_anonymous_problem_keeps_message_and_expired_status() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            410,
            json={"title": "Checkpoint expired", "status": 410, "detail": "Read without after_id"},
        )

    with (
        AtraxisClient(token="", transport=httpx.MockTransport(handle)) as client,
        pytest.raises(AtraxisAPIError, match="Checkpoint expired") as failure,
    ):
        client.get_announcements(after_id="1")
    assert failure.value.status_code == 410
    assert "[REDACTED]" not in str(failure.value)


def test_required_public_fields_do_not_become_empty_success() -> None:
    with (
        AtraxisClient(
            token="",
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"items": []})),
        ) as client,
        pytest.raises(AtraxisResponseError),
    ):
        client.get_events()


async def test_async_anonymous_iteration() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert "authorization" not in request.headers
        return httpx.Response(200, json=announcement_page())

    async with AsyncAtraxisClient(token="", transport=httpx.MockTransport(handle)) as client:
        assert [item.id async for item in client.iter_new_announcements(after_id="0")] == ["1"]


async def test_mcp_public_tools_execute_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    from atraxis import mcp_server

    def client(token: str | None, base_url: str | None) -> AsyncAtraxisClient:
        return AsyncAtraxisClient(
            token="",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=announcement_page())
            ),
        )

    monkeypatch.setattr(mcp_server, "_client", client)
    server = build_server(token=None, base_url=None, allow_writes=False)
    async with Client(server) as session:  # type: ignore[arg-type]
        result = await session.call_tool(
            "atraxis_get_announcements", {"after_id": "0", "order": "asc"}
        )
    assert result.is_error is False
    assert result.structured_content is not None
    assert result.structured_content["checkpoint"] == "1"
