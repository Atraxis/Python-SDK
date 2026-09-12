"""Safe, typed errors raised by the Atraxis clients."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


class AtraxisError(Exception):
    """Base exception for all SDK failures."""


@dataclass(frozen=True, slots=True)
class Problem:
    type: str
    title: str
    status: int
    detail: str | None = None
    request_id: str | None = None

    @classmethod
    def from_payload(
        cls,
        payload: object,
        *,
        status: int,
        request_id: str | None,
    ) -> Problem:
        data: Mapping[str, Any] = payload if isinstance(payload, Mapping) else {}
        return cls(
            type=_safe_text(data.get("type"), "about:blank"),
            title=_safe_text(data.get("title"), "Atraxis API rejected the request"),
            status=status,
            detail=_optional_text(data.get("detail")),
            request_id=request_id or _optional_text(data.get("request_id")),
        )


class AtraxisAPIError(AtraxisError):
    """An HTTP problem response from Atraxis."""

    def __init__(self, problem: Problem) -> None:
        self.problem = problem
        message = f"{problem.status}: {problem.title}"
        if problem.detail:
            message = f"{message} — {problem.detail}"
        if problem.request_id:
            message = f"{message} (request_id={problem.request_id})"
        super().__init__(message)

    @property
    def status_code(self) -> int:
        return self.problem.status

    @property
    def request_id(self) -> str | None:
        return self.problem.request_id


class AtraxisTransportError(AtraxisError):
    """A network failure after the bounded retry policy was exhausted."""

    def __init__(self, message: str = "Could not reach Atraxis API") -> None:
        super().__init__(message)


class AtraxisResponseError(AtraxisError):
    """The server returned a successful response that violates the public contract."""

    def __init__(self, request_id: str | None = None) -> None:
        self.request_id = request_id
        message = "Atraxis API returned an invalid response"
        if request_id:
            message = f"{message} (request_id={request_id})"
        super().__init__(message)


def _safe_text(value: object, fallback: str) -> str:
    return value if isinstance(value, str) and value else fallback


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
