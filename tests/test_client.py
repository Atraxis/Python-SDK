from __future__ import annotations

import json
import logging

import httpx
import pytest

from atraxis import (
    AsyncAtraxisClient,
    AtraxisAPIError,
    AtraxisClient,
    AtraxisResponseError,
    CurrencyTransfer,
    ItemTransfer,
    __version__,
)
from atraxis.models import ActivityAsset

TOKEN = "agk_example.redacted"
BASE_URL = "https://example.test/api/external/v1"


def warehouse(*, next_cursor: str | None = None) -> dict[str, object]:
    result: dict[str, object] = {
        "slots_used": 1,
        "slots_total": 50,
        "items": [
            {
                "warehouse_item_id": "700001",
                "item_id": "200001",
                "name": "Test item",
                "quantity": 2,
                "durability": 3,
                "max_durability": 5,
                "transfer_restricted": False,
                "future_additive_field": "accepted",
            }
        ],
        "future_additive_field": True,
    }
    if next_cursor:
        result["next_cursor"] = next_cursor
    return result


def json_response(payload: object, status: int = 200, **headers: str) -> httpx.Response:
    return httpx.Response(status, json=payload, headers=headers)


def test_sync_client_paginates_and_uses_header_auth_without_secret_repr() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return json_response(warehouse(next_cursor="next" if len(requests) == 1 else None))

    with AtraxisClient(TOKEN, base_url=BASE_URL, transport=httpx.MockTransport(handler)) as client:
        items = list(client.iter_warehouse(page_size=25))
        assert TOKEN not in repr(client)

    assert [item.warehouse_item_id for item in items] == [700001, 700001]
    assert requests[0].headers["Authorization"] == f"Bearer {TOKEN}"
    assert requests[0].headers["User-Agent"] == f"atraxis-sdk/{__version__}"
    assert requests[0].url.params["page_size"] == "25"
    assert requests[1].url.params["cursor"] == "next"


def test_currency_configuration_has_only_user_facing_fields() -> None:
    seen: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen = request
        return json_response(
            {
                "code": "TOKEN",
                "name": "Token",
                "transferable": True,
                "total_supply": "9000000000000000",
                "treasury_balance": "0",
            }
        )

    with AtraxisClient(TOKEN, base_url=BASE_URL, transport=httpx.MockTransport(handler)) as client:
        currency = client.upsert_currency(
            "TOKEN",
            name="Token",
            transferable=True,
        )

    assert currency.total_supply == 9_000_000_000_000_000
    assert seen is not None
    assert json.loads(seen.content) == {"name": "Token", "transferable": True}


def test_transfer_generates_key_and_keeps_it_across_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    keys: list[str] = []
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        keys.append(request.headers["Idempotency-Key"])
        if calls == 1:
            return json_response(
                {"type": "about:blank", "title": "Busy", "status": 503, "request_id": "r-1"},
                503,
                **{"Retry-After": "0"},
            )
        body = json.loads(request.content)
        return json_response(
            {
                "operation_id": "00000000-0000-4000-8000-000000000010",
                "transfers": [
                    {
                        "index": 0,
                        "asset": body["transfers"][0]["asset"],
                        "from": body["transfers"][0]["from"],
                        "to": body["transfers"][0]["to"],
                        "amount": body["transfers"][0]["amount"],
                    }
                ],
            },
            **{"X-Request-ID": "r-2", "Idempotency-Replayed": "true"},
        )

    monkeypatch.setattr("atraxis._transport.time.sleep", lambda _delay: None)
    with AtraxisClient(TOKEN, base_url=BASE_URL, transport=httpx.MockTransport(handler)) as client:
        result = client.transfer([ItemTransfer(warehouse_item_id=7, player_id=42)])

    assert calls == 2
    assert keys[0] == keys[1] == result.idempotency_key
    assert result.replayed is True
    assert result.request_id == "r-2"
    assert result.transfers[0].amount == 1
    assert result.idempotency_key not in repr(result)


def test_problem_and_logging_do_not_expose_token(caplog: pytest.LogCaptureFixture) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return json_response(
            {
                "type": "urn:atraxis:problem:not-found",
                "title": "Not found",
                "status": 404,
                "detail": f"Resource is unavailable: {TOKEN}",
                "request_id": "request-safe",
            },
            404,
        )

    caplog.set_level(logging.DEBUG)
    with (
        AtraxisClient(TOKEN, base_url=BASE_URL, transport=httpx.MockTransport(handler)) as client,
        pytest.raises(AtraxisAPIError) as caught,
    ):
        client.get_balances(42)

    assert caught.value.status_code == 404
    assert caught.value.request_id == "request-safe"
    assert TOKEN not in str(caught.value)
    assert "[REDACTED]" in str(caught.value)
    assert TOKEN not in caplog.text


def test_idempotency_key_rejects_outer_whitespace() -> None:
    transport = httpx.MockTransport(lambda _request: json_response({}))
    with (
        AtraxisClient(TOKEN, base_url=BASE_URL, transport=transport) as client,
        pytest.raises(ValueError),
    ):
        client.transfer(
            [ItemTransfer(warehouse_item_id=7, player_id=42)],
            idempotency_key=" order-1 ",
        )


def test_required_response_fields_are_validated() -> None:
    transport = httpx.MockTransport(lambda _request: json_response({"items": []}))
    with (
        AtraxisClient(TOKEN, base_url=BASE_URL, transport=transport) as client,
        pytest.raises(AtraxisResponseError),
    ):
        client.get_warehouse()


@pytest.mark.asyncio
async def test_async_client_and_activity_pagination() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return json_response(
            {
                "items": [
                    {
                        "event_id": "00000000-0000-4000-8000-000000000001",
                        "occurred_at": "2026-09-12T10:00:00Z",
                        "operation_id": "00000000-0000-4000-8000-000000000002",
                        "kind": "currency_transfer",
                        "source": "api",
                        "from": {"type": "guild"},
                        "to": {"type": "player", "player_id": "42"},
                        "asset": {"type": "guild_currency", "currency_code": "TOKEN"},
                        "gross": "25",
                        "fee": "0",
                        "net": "25",
                        "balance_before": "100",
                        "balance_after": "75",
                        "leg_index": 0,
                    }
                ]
            }
        )

    transport = httpx.MockTransport(handler)
    async with AsyncAtraxisClient(TOKEN, base_url=BASE_URL, transport=transport) as client:
        events = [event async for event in client.iter_activity(page_size=1)]
        with pytest.raises(ValueError):
            await client.get_balances(0)

    assert events[0].net == 25
    assert events[0].to_party.player_id == 42
    assert requests[0].url.path.endswith("/activity")


def test_transfer_builders_cover_all_public_directions() -> None:
    transfers = [
        CurrencyTransfer.issue("TOKEN", amount=5),
        CurrencyTransfer.retire("TOKEN", amount=5),
        CurrencyTransfer.to_player("TOKEN", player_id=1, amount=5),
        CurrencyTransfer.from_player("TOKEN", player_id=1, amount=5),
        CurrencyTransfer.between_players("TOKEN", from_player_id=1, to_player_id=2, amount=5),
    ]
    assert [(item.from_party.type, item.to_party.type) for item in transfers] == [
        ("supply", "guild"),
        ("guild", "supply"),
        ("guild", "player"),
        ("player", "guild"),
        ("player", "player"),
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "game_item"},
        {"type": "guild_currency"},
    ],
)
def test_activity_asset_requires_fields_for_its_type(payload: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        ActivityAsset.from_dict(payload)
