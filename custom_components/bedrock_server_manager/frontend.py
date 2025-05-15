# custom_components/bedrock_server_manager/frontend.py
"""Frontend registration for BSM Manager."""

import logging
import os
from pathlib import Path
from typing import Optional

from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace import LovelaceData
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import UNDEFINED

from .const import DOMAIN, FRONTEND_URL_BASE, JS_MODULES

_LOGGER = logging.getLogger(__name__)


class BsmFrontendRegistration:
    """Register BSM Javascript modules."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise."""
        self.hass = hass
        # Lovelace storage data might be under a different key or need specific loading
        # Let's use the recommended way to get the Lovelace instance
        self.lovelace: Optional[Lovelace] = hass.data.get("lovelace")
        if not self.lovelace:
            _LOGGER.warning(
                "Lovelace storage backend not found or not loaded yet. Cannot auto-register frontend modules."
            )

    async def async_register(self):
        """Register static path and Lovelace resources if needed."""
        if not self.lovelace:
            _LOGGER.warning("Cannot register frontend modules: Lovelace not available.")
            return  # Cannot proceed if lovelace isn't loaded

        await self._async_register_static_path()

        # Auto-registration only works/makes sense in storage mode
        if self.lovelace.mode == "storage":
            await self._async_wait_for_lovelace_resources()
        else:
            _LOGGER.info(
                "Lovelace is in YAML mode. Manual resource registration required for BSM cards."
            )

    async def _async_register_static_path(self):
        """Register resource path if not already registered."""
        path_registered = any(
            route.path == FRONTEND_URL_BASE
            for route in self.hass.http.app.router.routes()
            if route.name == "static"  # Check name added by async_register_static_paths
        )

        if path_registered:
            _LOGGER.debug(
                "Frontend static path %s already registered.", FRONTEND_URL_BASE
            )
            return

        try:
            # Register static path pointing to the 'frontend' directory
            frontend_dir = Path(__file__).parent / "frontend"
            if not frontend_dir.is_dir():
                _LOGGER.error(
                    "Frontend directory missing at %s. Cannot register static path.",
                    frontend_dir,
                )
                return

            await self.hass.http.async_register_static_paths(
                [
                    StaticPathConfig(
                        FRONTEND_URL_BASE, str(frontend_dir), cache_headers=False
                    )
                ]  # Use str() for path
            )
            _LOGGER.info(
                "Registered frontend static path: %s -> %s",
                FRONTEND_URL_BASE,
                frontend_dir,
            )
        except RuntimeError:
            # Should be caught by check above, but handle defensively
            _LOGGER.debug(
                "Frontend static path %s already registered (runtime error).",
                FRONTEND_URL_BASE,
            )
        except Exception as e:
            _LOGGER.error(
                "Error registering static path %s: %s",
                FRONTEND_URL_BASE,
                e,
                exc_info=True,
            )

    async def _async_wait_for_lovelace_resources(self) -> None:
        """Wait for lovelace resources to have loaded before registering modules."""

        async def _check_lovelace_resources_loaded(now=None):  # Add default for now
            # Access resources via the Lovelace storage manager
            if (
                self.lovelace and self.lovelace.resources
            ):  # Check if resources are loaded
                if self.lovelace.resources.loaded:
                    await self._async_register_modules()
                    return  # Stop checking

            # If not loaded yet, schedule retry
            _LOGGER.debug(
                "Lovelace resources not yet loaded. Retrying module registration in 5 seconds."
            )
            async_call_later(self.hass, 5, _check_lovelace_resources_loaded)

        # Start the check
        await _check_lovelace_resources_loaded()

    async def _async_register_modules(self):
        """Register modules in Lovelace resources if not already registered."""
        if not self.lovelace or not self.lovelace.resources:
            _LOGGER.error("Cannot register modules: Lovelace resources not available.")
            return

        _LOGGER.info("Checking/Registering BSM javascript modules in Lovelace")
        current_resources = self.lovelace.resources.async_items()

        for module in JS_MODULES:
            # Construct the full URL with version query string for cache busting
            module_url = (
                f"{FRONTEND_URL_BASE}/{module['filename']}?v={module['version']}"
            )
            module_registered = False
            resource_id_to_update = None
            current_version = None

            for resource in current_resources:
                # Compare base URL path without version query string
                if self._get_resource_path(resource["url"]) == self._get_resource_path(
                    module_url
                ):
                    module_registered = True
                    current_version = self._get_resource_version(resource["url"])
                    if current_version != module["version"]:
                        resource_id_to_update = resource["id"]
                    break  # Found resource for this module

            if not module_registered:
                _LOGGER.info("Registering new Lovelace module: %s", module_url)
                try:
                    await self.lovelace.resources.async_create_item(
                        {"res_type": "module", "url": module_url}
                    )
                except Exception as e:
                    _LOGGER.error(
                        "Error registering Lovelace module %s: %s",
                        module_url,
                        e,
                        exc_info=True,
                    )
            elif resource_id_to_update:
                _LOGGER.info(
                    "Updating Lovelace module %s from version %s to %s",
                    module["name"],
                    current_version,
                    module["version"],
                )
                try:
                    await self.lovelace.resources.async_update_item(
                        resource_id_to_update,
                        {
                            "res_type": "module",
                            "url": module_url,
                        },  # Update URL with new version
                    )
                except Exception as e:
                    _LOGGER.error(
                        "Error updating Lovelace module %s: %s",
                        module_url,
                        e,
                        exc_info=True,
                    )
            else:
                _LOGGER.debug(
                    "%s version %s already registered.",
                    module["name"],
                    module["version"],
                )

    def _get_resource_path(self, url: str):
        """Extract path part before query string."""
        return url.split("?")[0]

    def _get_resource_version(self, url: str):
        """Extract version from query string (v=...). Returns '0' if not found."""
        parts = url.split("?")
        if len(parts) > 1:
            query_params = parts[1].split("&")
            for param in query_params:
                if param.startswith("v="):
                    return param[2:]  # Return value after 'v='
        return "0"  # Default if no version found

    async def async_unregister(self):
        """Unload lovelace module resource."""
        if not self.lovelace or self.lovelace.mode != "storage":
            return  # Only unregister from storage mode

        _LOGGER.info("Unregistering BSM javascript modules from Lovelace")
        current_resources = self.lovelace.resources.async_items()

        for module in JS_MODULES:
            module_base_url = f"{FRONTEND_URL_BASE}/{module['filename']}"
            resources_to_remove = [
                resource
                for resource in current_resources
                if self._get_resource_path(resource["url"]) == module_base_url
            ]
            for resource in resources_to_remove:
                try:
                    _LOGGER.debug(
                        "Deleting Lovelace resource: ID=%s, URL=%s",
                        resource["id"],
                        resource["url"],
                    )
                    await self.lovelace.resources.async_delete_item(resource["id"])
                except Exception as e:
                    _LOGGER.error(
                        "Error deleting Lovelace resource %s: %s",
                        resource["url"],
                        e,
                        exc_info=True,
                    )
