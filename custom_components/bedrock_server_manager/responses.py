"""Versioned action outcomes with safe, structured SDK failures."""

from typing import Any, Literal

from bsm_api_client import APIError, CannotConnectError
from pydantic import BaseModel, Field, ValidationError

from .coordinator import json_data


class ActionError(BaseModel):
    """Describe a failure without copying request bodies or credentials."""

    message: str
    code: str
    type: str
    status_code: int | None = None
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class TargetResult(BaseModel):
    """Keep target identity separate from its backend result."""

    manager_url: str
    server_name: str | None = None
    status: Literal["success", "failed", "partial", "skipped"] = "success"
    result: Any = None
    error: dict[str, Any] | None = None
    warnings: list[dict[str, Any]] = Field(default_factory=list)


def _safe_details(value: Any, depth: int = 0) -> Any:
    """Bound diagnostic details and omit values carried by validation errors."""
    if depth > 8:
        return None
    if isinstance(value, dict):
        return {
            str(key): _safe_details(item, depth + 1)
            for key, item in list(value.items())[:100]
            if str(key).lower() not in {"input", "ctx", "body", "request", "value"}
            and not any(
                term in str(key).lower()
                for term in ("password", "token", "secret", "authorization")
            )
        }
    if isinstance(value, (list, tuple)):
        return [_safe_details(item, depth + 1) for item in value[:100]]
    if isinstance(value, str):
        return value[:4096]
    return value if value is None or isinstance(value, (bool, int, float)) else None


def action_error(error: Exception) -> dict[str, Any]:
    """Retain API codes and validation locations without transport internals."""
    details: dict[str, Any] = {}
    status = getattr(error, "status_code", None)
    code = getattr(error, "api_code", None) or type(error).__name__
    if isinstance(error, ValidationError):
        message = "Request validation failed"
        details = {
            "validation": error.errors(include_input=False, include_context=False)
        }
    elif isinstance(error, APIError):
        message = error.api_message or "The BSM API request failed"
        if error.committed:
            message += ". The change was saved, but follow-up work failed. Refresh before trying again."
        details = _safe_details(error.api_details)
        if error.api_errors:
            details["validation"] = _safe_details(error.api_errors)
    elif isinstance(error, (OSError, TimeoutError)):
        message = "BSM is unavailable or the request timed out"
    else:
        message = str(error)
    return ActionError(
        message=message,
        code=code,
        type=type(error).__name__,
        status_code=status,
        retryable=not getattr(error, "committed", False)
        and (
            isinstance(error, (CannotConnectError, TimeoutError))
            or status == 429
            or (status is not None and status >= 500)
        ),
        details=details,
    ).model_dump(exclude_none=True)


def target_result(manager_url: str, result: Any = None, **kwargs: Any) -> dict:
    """Build a JSON-safe target envelope shared by response actions."""
    payload = json_data(result)
    status = payload.get("status") if isinstance(payload, dict) else None
    if status in {"partial", "skipped"} and "status" not in kwargs:
        kwargs["status"] = status
    return TargetResult(manager_url=manager_url, result=payload, **kwargs).model_dump(
        exclude_none=True
    )


def action_response(results: list[dict], **legacy: Any) -> dict:
    """Keep old response aliases while introducing the common versioned envelope."""
    return {"response_schema_version": 1, "results": results, **legacy}
