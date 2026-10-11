"Typed SDK action common for HA services."

import logging
from typing import Any, Coroutine, Optional

from bsm_api_client import (
    APIError,
    AuthError,
    CannotConnectError,
    InvalidInputError,
    ServerNotFoundError,
    ServerNotRunningError,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

_LOGGER = logging.getLogger(__name__)


async def _base_api_call_handler(
    api_call_coro: Coroutine[Any, Any, Any],
    error_message_prefix: str,
    log_context_identifier: Optional[str] = None,
) -> Any:
    context_msg = f" for '{log_context_identifier}'" if log_context_identifier else ""
    try:
        response = await api_call_coro
        status = (
            response.get("status")
            if isinstance(response, dict)
            else getattr(response, "status", None)
        )
        if status in ("error", "failed", "failure"):
            raise HomeAssistantError(
                f"{error_message_prefix}{context_msg}: API reported {status}"
            )
        _LOGGER.debug(
            "API call %s successful%s",
            error_message_prefix,
            context_msg,
        )
        return response
    except HomeAssistantError:
        raise
    except (APIError, ValueError) as err:
        details = _api_error_details(err)
        msg = f"{error_message_prefix}{context_msg}: {details}"
        _LOGGER.error(msg)
        error_type = (
            ServiceValidationError
            if isinstance(err, (InvalidInputError, ValueError))
            else HomeAssistantError
        )
        raise error_type(msg) from err
    except Exception as err:
        _LOGGER.exception("%s%s: Unexpected error.", error_message_prefix, context_msg)
        raise HomeAssistantError(
            f"{error_message_prefix}{context_msg}: Unexpected error - {type(err).__name__}"
        ) from err


def _api_error_details(err: APIError | ValueError) -> str:
    """Describe an SDK failure without exposing transport internals."""
    if isinstance(err, ValueError):
        return f"Invalid input value provided. ({err})"
    if isinstance(err, AuthError) and err.status_code == 403:
        return "The BSM account does not have permission for this action"
    descriptions = (
        (ServerNotRunningError, "Server is not running"),
        (ServerNotFoundError, "Target server not found by API"),
        (InvalidInputError, "Invalid input provided"),
        (AuthError, "Authentication failed"),
        (CannotConnectError, "Cannot connect to BSM API"),
    )
    for error_type, description in descriptions:
        if isinstance(err, error_type):
            return f"{description}. ({err.api_message or err})"
    return f"BSM API error (status: {err.status_code}). ({err.api_message or err})"
