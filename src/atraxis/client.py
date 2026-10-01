"""Synchronous and asynchronous Atraxis API clients."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Iterator, Mapping, Sequence
from typing import Any
from urllib.parse import quote

import httpx

from ._transport import (
    AsyncTransport,
    QueryValue,
    SyncTransport,
    object_payload,
    response_request_id,
)
from .errors import AtraxisResponseError
from .models import (
    CURRENCY_CODE_PATTERN,
    ActivityEvent,
    ActivityPage,
    Currency,
    PlayerBalances,
    TransferInput,
    TransferResult,
    Warehouse,
    WarehouseItem,
)

DEFAULT_BASE_URL = "https://atraxisonline.com/api/external/v1"


def _configuration(token: str | None, base_url: str | None) -> tuple[str, str]:
    resolved_token = token if token is not None else os.getenv("ATRAXIS_API_TOKEN", "")
    resolved_token = resolved_token.strip()
    if not resolved_token:
        raise ValueError("Atraxis API token is required")
    resolved_base = (base_url or os.getenv("ATRAXIS_API_BASE_URL") or DEFAULT_BASE_URL).strip()
    if not resolved_base:
        raise ValueError("Atraxis API base URL is required")
    parsed = httpx.URL(resolved_base)
    if parsed.scheme not in {"http", "https"} or not parsed.host:
        raise ValueError("Atraxis API base URL must be an absolute HTTP(S) URL")
    return resolved_token, resolved_base.rstrip("/") + "/"


def _page_size(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 100:
        raise ValueError("page_size must be between 1 and 100")
    return value


def _player_id(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("player_id must be a positive integer")
    return value


def _currency_update(code: str, name: str, transferable: bool) -> dict[str, object]:
    if not CURRENCY_CODE_PATTERN.fullmatch(code):
        raise ValueError("code must match [A-Z][A-Z0-9_]{0,15}")
    normalized_name = name.strip()
    if not normalized_name or len(normalized_name) > 64:
        raise ValueError("name must contain between 1 and 64 characters")
    if not isinstance(transferable, bool):
        raise ValueError("transferable must be a boolean")
    return {
        "name": normalized_name,
        "transferable": transferable,
    }


def _currency_list(payload: Mapping[str, Any], request_id: str | None) -> tuple[Currency, ...]:
    values = payload.get("items")
    if not isinstance(values, list):
        raise AtraxisResponseError(request_id)
    try:
        return tuple(Currency.from_dict(value) for value in values)
    except (TypeError, ValueError) as exc:
        raise AtraxisResponseError(request_id) from exc


def _transfer_body(transfers: Sequence[TransferInput]) -> dict[str, object]:
    if not 1 <= len(transfers) <= 10:
        raise ValueError("transfers must contain between 1 and 10 entries")
    return {"transfers": [transfer.to_wire() for transfer in transfers]}


def _optional_page_params(page_size: int, cursor: str | None) -> dict[str, QueryValue]:
    params: dict[str, QueryValue] = {"page_size": _page_size(page_size)}
    if cursor:
        params["cursor"] = cursor
    return params


def _activity_page_params(
    page_size: int,
    cursor: str | None,
    after_event_id: str | None,
    order: str,
) -> dict[str, QueryValue]:
    if order not in {"desc", "asc"}:
        raise ValueError("order must be 'desc' or 'asc'")
    params = _optional_page_params(page_size, cursor)
    params["order"] = order
    if after_event_id is not None:
        if not isinstance(after_event_id, str) or after_event_id != after_event_id.strip():
            raise ValueError("after_event_id must be an event_id from an activity response")
        try:
            parsed = uuid.UUID(after_event_id)
        except ValueError as exc:
            raise ValueError(
                "after_event_id must be an event_id from an activity response"
            ) from exc
        if parsed.int == 0 or str(parsed) != after_event_id:
            raise ValueError("after_event_id must be an event_id from an activity response")
        params["after_event_id"] = after_event_id
    return params


class AtraxisClient:
    """Small typed synchronous client. The token is never included in ``repr``."""

    def __init__(
        self,
        token: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float | httpx.Timeout = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        resolved_token, resolved_base = _configuration(token, base_url)
        self._transport = SyncTransport(
            token=resolved_token,
            base_url=resolved_base,
            timeout=timeout,
            transport=transport,
        )
        self._base_url = resolved_base

    def __repr__(self) -> str:
        return f"AtraxisClient(base_url={self._base_url!r})"

    def __enter__(self) -> AtraxisClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        self._transport.close()

    def get_warehouse(self) -> Warehouse:
        response = self._transport.request("GET", "warehouse")
        try:
            return Warehouse.from_dict(object_payload(response))
        except (TypeError, ValueError) as exc:
            raise AtraxisResponseError(response_request_id(response)) from exc

    def iter_warehouse(self) -> Iterator[WarehouseItem]:
        yield from self.get_warehouse().items

    def list_currencies(self) -> tuple[Currency, ...]:
        response = self._transport.request("GET", "currencies")
        return _currency_list(object_payload(response), response_request_id(response))

    def upsert_currency(
        self,
        code: str,
        *,
        name: str,
        transferable: bool,
    ) -> Currency:
        response = self._transport.request(
            "PUT",
            f"currencies/{quote(code, safe='')}",
            body=_currency_update(code, name, transferable),
        )
        try:
            return Currency.from_dict(object_payload(response))
        except (TypeError, ValueError) as exc:
            raise AtraxisResponseError(response_request_id(response)) from exc

    def get_balances(self, player_id: int) -> PlayerBalances:
        response = self._transport.request("GET", f"balances/{_player_id(player_id)}")
        try:
            return PlayerBalances.from_dict(object_payload(response))
        except (TypeError, ValueError) as exc:
            raise AtraxisResponseError(response_request_id(response)) from exc

    def transfer(
        self,
        transfers: Sequence[TransferInput],
        *,
        idempotency_key: str | None = None,
    ) -> TransferResult:
        key = idempotency_key or str(uuid.uuid4())
        if not key.strip() or key != key.strip() or len(key) > 255:
            raise ValueError("idempotency_key must contain between 1 and 255 characters")
        response = self._transport.request(
            "POST",
            "transfers",
            body=_transfer_body(transfers),
            idempotency_key=key,
        )
        try:
            return TransferResult.from_dict(
                object_payload(response),
                idempotency_key=key,
                request_id=response_request_id(response),
                replayed=response.headers.get("Idempotency-Replayed", "").lower() == "true",
            )
        except (TypeError, ValueError) as exc:
            raise AtraxisResponseError(response_request_id(response)) from exc

    def get_activity(
        self,
        *,
        page_size: int = 50,
        cursor: str | None = None,
        after_event_id: str | None = None,
        order: str = "desc",
    ) -> ActivityPage:
        response = self._transport.request(
            "GET",
            "activity",
            params=_activity_page_params(page_size, cursor, after_event_id, order),
        )
        try:
            return ActivityPage.from_dict(object_payload(response))
        except (TypeError, ValueError) as exc:
            raise AtraxisResponseError(response_request_id(response)) from exc

    def iter_activity(
        self,
        *,
        page_size: int = 50,
        after_event_id: str | None = None,
        order: str = "desc",
    ) -> Iterator[ActivityEvent]:
        cursor: str | None = None
        while True:
            page = self.get_activity(
                page_size=page_size,
                cursor=cursor,
                after_event_id=after_event_id,
                order=order,
            )
            yield from page.items
            if not page.next_cursor:
                return
            cursor = page.next_cursor

    def iter_new_activity(
        self,
        *,
        after_event_id: str,
        page_size: int = 50,
    ) -> Iterator[ActivityEvent]:
        yield from self.iter_activity(
            page_size=page_size,
            after_event_id=after_event_id,
            order="asc",
        )


class AsyncAtraxisClient:
    """Small typed asynchronous client. The token is never included in ``repr``."""

    def __init__(
        self,
        token: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float | httpx.Timeout = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        resolved_token, resolved_base = _configuration(token, base_url)
        self._transport = AsyncTransport(
            token=resolved_token,
            base_url=resolved_base,
            timeout=timeout,
            transport=transport,
        )
        self._base_url = resolved_base

    def __repr__(self) -> str:
        return f"AsyncAtraxisClient(base_url={self._base_url!r})"

    async def __aenter__(self) -> AsyncAtraxisClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._transport.close()

    async def get_warehouse(self) -> Warehouse:
        response = await self._transport.request("GET", "warehouse")
        try:
            return Warehouse.from_dict(object_payload(response))
        except (TypeError, ValueError) as exc:
            raise AtraxisResponseError(response_request_id(response)) from exc

    async def iter_warehouse(self) -> AsyncIterator[WarehouseItem]:
        for item in (await self.get_warehouse()).items:
            yield item

    async def list_currencies(self) -> tuple[Currency, ...]:
        response = await self._transport.request("GET", "currencies")
        return _currency_list(object_payload(response), response_request_id(response))

    async def upsert_currency(
        self,
        code: str,
        *,
        name: str,
        transferable: bool,
    ) -> Currency:
        response = await self._transport.request(
            "PUT",
            f"currencies/{quote(code, safe='')}",
            body=_currency_update(code, name, transferable),
        )
        try:
            return Currency.from_dict(object_payload(response))
        except (TypeError, ValueError) as exc:
            raise AtraxisResponseError(response_request_id(response)) from exc

    async def get_balances(self, player_id: int) -> PlayerBalances:
        response = await self._transport.request("GET", f"balances/{_player_id(player_id)}")
        try:
            return PlayerBalances.from_dict(object_payload(response))
        except (TypeError, ValueError) as exc:
            raise AtraxisResponseError(response_request_id(response)) from exc

    async def transfer(
        self,
        transfers: Sequence[TransferInput],
        *,
        idempotency_key: str | None = None,
    ) -> TransferResult:
        key = idempotency_key or str(uuid.uuid4())
        if not key.strip() or key != key.strip() or len(key) > 255:
            raise ValueError("idempotency_key must contain between 1 and 255 characters")
        response = await self._transport.request(
            "POST",
            "transfers",
            body=_transfer_body(transfers),
            idempotency_key=key,
        )
        try:
            return TransferResult.from_dict(
                object_payload(response),
                idempotency_key=key,
                request_id=response_request_id(response),
                replayed=response.headers.get("Idempotency-Replayed", "").lower() == "true",
            )
        except (TypeError, ValueError) as exc:
            raise AtraxisResponseError(response_request_id(response)) from exc

    async def get_activity(
        self,
        *,
        page_size: int = 50,
        cursor: str | None = None,
        after_event_id: str | None = None,
        order: str = "desc",
    ) -> ActivityPage:
        response = await self._transport.request(
            "GET",
            "activity",
            params=_activity_page_params(page_size, cursor, after_event_id, order),
        )
        try:
            return ActivityPage.from_dict(object_payload(response))
        except (TypeError, ValueError) as exc:
            raise AtraxisResponseError(response_request_id(response)) from exc

    async def iter_activity(
        self,
        *,
        page_size: int = 50,
        after_event_id: str | None = None,
        order: str = "desc",
    ) -> AsyncIterator[ActivityEvent]:
        cursor: str | None = None
        while True:
            page = await self.get_activity(
                page_size=page_size,
                cursor=cursor,
                after_event_id=after_event_id,
                order=order,
            )
            for item in page.items:
                yield item
            if not page.next_cursor:
                return
            cursor = page.next_cursor

    async def iter_new_activity(
        self,
        *,
        after_event_id: str,
        page_size: int = 50,
    ) -> AsyncIterator[ActivityEvent]:
        async for item in self.iter_activity(
            page_size=page_size,
            after_event_id=after_event_id,
            order="asc",
        ):
            yield item
