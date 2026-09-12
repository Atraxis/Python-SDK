"""Shared bounded transport policy for sync and async clients."""

from __future__ import annotations

import asyncio
import email.utils
import json
import time
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, cast

import httpx

from .errors import AtraxisAPIError, AtraxisResponseError, AtraxisTransportError, Problem

RETRYABLE_STATUSES = frozenset({429, 502, 503, 504})
MAX_RETRIES = 2
MAX_RETRY_DELAY_SECONDS = 30.0
QueryValue = str | int | float | bool | None


def response_request_id(response: httpx.Response) -> str | None:
    return cast(str | None, response.headers.get("X-Request-ID"))


def response_json(response: httpx.Response) -> object:
    try:
        return response.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise AtraxisResponseError(response_request_id(response)) from exc


def _redact(value: object, token: str) -> object:
    if isinstance(value, str):
        return value.replace(token, "[REDACTED]")
    if isinstance(value, list):
        return [_redact(item, token) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _redact(item, token) for key, item in value.items()}
    return value


def raise_for_problem(response: httpx.Response, token: str) -> None:
    if response.is_success:
        return
    try:
        payload = _redact(response.json(), token)
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = {}
    raise AtraxisAPIError(
        Problem.from_payload(
            payload,
            status=response.status_code,
            request_id=response_request_id(response),
        )
    )


def retry_delay(response: httpx.Response | None, attempt: int) -> float:
    if response is not None:
        value = response.headers.get("Retry-After")
        if value:
            try:
                seconds = float(value)
            except ValueError:
                try:
                    parsed = email.utils.parsedate_to_datetime(value)
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    seconds = (parsed - datetime.now(timezone.utc)).total_seconds()
                except (TypeError, ValueError, OverflowError):
                    seconds = -1
            if seconds >= 0:
                return seconds if seconds < MAX_RETRY_DELAY_SECONDS else MAX_RETRY_DELAY_SECONDS
    delay = 0.25 * float(2**attempt)
    return delay if delay < MAX_RETRY_DELAY_SECONDS else MAX_RETRY_DELAY_SECONDS


def safe_headers(token: str, *, idempotency_key: str | None = None) -> dict[str, str]:
    headers = {
        "Accept": "application/json, application/problem+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "atraxis-sdk/0.1.0",
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return headers


class SyncTransport:
    def __init__(
        self,
        *,
        token: str,
        base_url: str,
        timeout: float | httpx.Timeout,
        transport: httpx.BaseTransport | None,
    ) -> None:
        self._token = token
        self._client = httpx.Client(base_url=base_url, timeout=timeout, transport=transport)

    def close(self) -> None:
        self._client.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, QueryValue] | None = None,
        body: object | None = None,
        idempotency_key: str | None = None,
    ) -> httpx.Response:
        response: httpx.Response | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self._client.request(
                    method,
                    path,
                    params=params,
                    json=body,
                    headers=safe_headers(self._token, idempotency_key=idempotency_key),
                )
            except httpx.TransportError:
                if attempt >= MAX_RETRIES:
                    raise AtraxisTransportError() from None
                time.sleep(retry_delay(None, attempt))
                continue
            if response.status_code not in RETRYABLE_STATUSES or attempt >= MAX_RETRIES:
                raise_for_problem(response, self._token)
                return response
            time.sleep(retry_delay(response, attempt))
        raise AtraxisTransportError()


class AsyncTransport:
    def __init__(
        self,
        *,
        token: str,
        base_url: str,
        timeout: float | httpx.Timeout,
        transport: httpx.AsyncBaseTransport | None,
    ) -> None:
        self._token = token
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, transport=transport)

    async def close(self) -> None:
        await self._client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, QueryValue] | None = None,
        body: object | None = None,
        idempotency_key: str | None = None,
    ) -> httpx.Response:
        response: httpx.Response | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await self._client.request(
                    method,
                    path,
                    params=params,
                    json=body,
                    headers=safe_headers(self._token, idempotency_key=idempotency_key),
                )
            except httpx.TransportError:
                if attempt >= MAX_RETRIES:
                    raise AtraxisTransportError() from None
                await asyncio.sleep(retry_delay(None, attempt))
                continue
            if response.status_code not in RETRYABLE_STATUSES or attempt >= MAX_RETRIES:
                raise_for_problem(response, self._token)
                return response
            await asyncio.sleep(retry_delay(response, attempt))
        raise AtraxisTransportError()


def object_payload(response: httpx.Response) -> Mapping[str, Any]:
    payload = response_json(response)
    if not isinstance(payload, Mapping):
        raise AtraxisResponseError(response_request_id(response))
    return payload
