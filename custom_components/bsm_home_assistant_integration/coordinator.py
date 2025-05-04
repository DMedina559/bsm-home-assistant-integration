"""DataUpdateCoordinator for the Minecraft Bedrock Server Manager integration."""

import asyncio
import logging
from datetime import timedelta

import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import (
    MinecraftBedrockApi,
    APIError,
    AuthError,
    CannotConnectError,
    ServerNotFoundError,
    ServerNotRunningError,
)

_LOGGER = logging.getLogger(__name__)


class MinecraftBedrockCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Minecraft Server Manager API."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: MinecraftBedrockApi,
        server_name: str,
        scan_interval: int,
    ) -> None:
        """Initialize the coordinator."""
        self.api = api_client  # Store the API client instance
        self.server_name = server_name
        self._scan_interval = scan_interval

        super().__init__(
            hass,
            _LOGGER,
            name=f"Minecraft Manager Coordinator ({server_name})",
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from API endpoint.

        This is the place to fetch data from your device API to update Home Assistant entities.
        """
        _LOGGER.debug("Coordinator requesting update for server '%s'", self.server_name)
        try:
            # The api._request method handles token presence and 401 retry internally
            # Timeout slightly less than interval to prevent overlap
            async with async_timeout.timeout(self._scan_interval - 5):
                # Use self.api and self.server_name stored during __init__
                status_info = await self.api.async_get_server_status_info(
                    self.server_name
                )
                # Expects {"status": "success", "process_info": {...} or null} on success
                return status_info

        except AuthError as err:
            # Raising ConfigEntryAuthFailed will prompt user for re-authentication
            _LOGGER.error(
                "Authentication error fetching data for %s: %s", self.server_name, err
            )
            raise ConfigEntryAuthFailed(
                f"Authentication failed for {self.server_name}: {err}"
            ) from err
        except ServerNotFoundError as err:
            # Server no longer found by API - potentially deleted on manager side
            _LOGGER.error(
                "Server %s not found by API during update: %s", self.server_name, err
            )
            raise UpdateFailed(f"Server {self.server_name} not found: {err}") from err
        except ServerNotRunningError as err:
            # Return specific structure indicating stopped state
            _LOGGER.debug(
                "Server %s is not running during update: %s", self.server_name, err
            )
            return {"status": "success", "process_info": None, "message": str(err)}
        except (APIError, CannotConnectError, asyncio.TimeoutError) as err:
            # Other API errors or connection issues
            _LOGGER.warning(
                "Error communicating with API for %s: %s", self.server_name, err
            )
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except Exception as err:
            # Catch-all for unexpected errors during update
            _LOGGER.exception(
                "Unexpected error fetching data for %s: %s", self.server_name, err
            )
            raise UpdateFailed(f"Unexpected error: {err}") from err
