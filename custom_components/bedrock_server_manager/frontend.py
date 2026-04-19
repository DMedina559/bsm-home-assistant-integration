"""Frontend Javascript module registration for Bedrock Server Manager."""

import logging
from pathlib import Path
from typing import Any

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later

from .const import FRONTEND_URL_BASE, JS_MODULES

_LOGGER = logging.getLogger(__name__)


class BsmFrontendRegistration:
    """Register BSM Javascript modules."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise."""
        self.hass = hass
        self.lovelace: Any = self.hass.data.get("lovelace")

    async def async_register(self) -> None:
        """Register frontend static path and Lovelace resources."""
        if not self.lovelace:
            _LOGGER.debug("Lovelace not loaded. Cannot register BSM frontend modules.")
            return

        await self._async_register_path()

        # Check if Lovelace is in storage mode (supports UI editing)
        lovelace_mode = getattr(
            self.lovelace, "mode", getattr(self.lovelace, "resource_mode", "yaml")
        )

        if lovelace_mode == "storage":
            await self._async_wait_for_lovelace_resources()
        else:
            _LOGGER.info(
                "Lovelace is in YAML mode. Manual resource registration required for BSM cards."
            )

    async def _async_register_path(self) -> None:
        """Register static resource path if not already registered."""
        frontend_dir = Path(__file__).parent / "frontend"
        try:
            await self.hass.http.async_register_static_paths(
                [
                    StaticPathConfig(
                        FRONTEND_URL_BASE, str(frontend_dir), cache_headers=False
                    )
                ]
            )
            _LOGGER.debug("Registered BSM frontend static path: %s", frontend_dir)
        except RuntimeError:
            # Runtime error means this path is already registered.
            _LOGGER.debug("BSM frontend static path already registered")

    async def _async_wait_for_lovelace_resources(self) -> None:
        """Wait for lovelace resources to finish loading before registering."""

        async def _check_lovelace_resources_loaded(_now: Any) -> None:
            if (
                self.lovelace
                and hasattr(self.lovelace, "resources")
                and self.lovelace.resources.loaded
            ):
                await self._async_register_modules()
            else:
                _LOGGER.debug(
                    "Lovelace resources not yet loaded. Trying again in 5 seconds."
                )
                async_call_later(self.hass, 5, _check_lovelace_resources_loaded)

        await _check_lovelace_resources_loaded(0)

    async def _async_register_modules(self) -> None:
        """Register modules if not already registered, or update if version changed."""
        _LOGGER.debug("Checking BSM javascript modules in Lovelace")

        # Get currently registered resources
        resources = [
            resource
            for resource in self.lovelace.resources.async_items()
            if str(resource["url"]).startswith(FRONTEND_URL_BASE)
        ]

        for module in JS_MODULES:
            url = f"{FRONTEND_URL_BASE}/{module.get('filename')}"
            target_version = module.get("version")
            target_url_with_version = f"{url}?v={target_version}"

            card_registered = False

            for resource in resources:
                if self._get_resource_path(resource["url"]) == url:
                    card_registered = True
                    current_version = self._get_resource_version(resource["url"])

                    if current_version != target_version:
                        # Update card version
                        _LOGGER.info(
                            "Updating %s to version %s",
                            module.get("name"),
                            target_version,
                        )
                        await self.lovelace.resources.async_update_item(
                            resource.get("id"),
                            {
                                "res_type": "module",
                                "url": target_url_with_version,
                            },
                        )
                    else:
                        _LOGGER.debug(
                            "%s already registered as version %s",
                            module.get("name"),
                            target_version,
                        )

            if not card_registered:
                _LOGGER.info(
                    "Registering %s as version %s",
                    module.get("name"),
                    target_version,
                )
                await self.lovelace.resources.async_create_item(
                    {"res_type": "module", "url": target_url_with_version}
                )

    def _get_resource_path(self, url: str) -> str:
        """Extract path part before the query string."""
        return url.split("?")[0]

    def _get_resource_version(self, url: str) -> str:
        """Safely extract version from query string (v=...)."""
        if "?" in url and "v=" in url:
            return url.split("v=")[1].split("&")[0]
        return "0"

    async def async_unregister(self) -> None:
        """Unload lovelace module resources when integration is removed."""
        if not self.lovelace:
            return

        lovelace_mode = getattr(
            self.lovelace, "mode", getattr(self.lovelace, "resource_mode", "yaml")
        )

        if lovelace_mode == "storage":
            for module in JS_MODULES:
                url = f"{FRONTEND_URL_BASE}/{module.get('filename')}"
                integration_resources = [
                    resource
                    for resource in self.lovelace.resources.async_items()
                    if str(resource["url"]).startswith(url)
                ]
                for resource in integration_resources:
                    _LOGGER.info("Unregistering Lovelace resource: %s", resource["url"])
                    await self.lovelace.resources.async_delete_item(resource.get("id"))
