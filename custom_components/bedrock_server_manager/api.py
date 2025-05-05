"""API Client for the Bedrock Server Manager."""

import aiohttp
import logging
from typing import Any, Dict, Optional, List

_LOGGER = logging.getLogger(__name__)


# --- Custom Exceptions ---
class APIError(Exception):
    """Generic API Error."""

    pass


class AuthError(APIError):
    """Authentication Error (e.g., 401 Unauthorized, Bad Credentials)."""

    pass


class ServerNotFoundError(APIError):
    """Server name not found (e.g., 404 on server-specific endpoint or validation)."""

    pass


class ServerNotRunningError(APIError):
    """Operation requires server to be running, but it is not."""

    pass


class CannotConnectError(APIError):
    """Error connecting to the API host."""

    pass


# --- API Client Class ---
class BedrockServerManagerApi:
    """Class to communicate with the Bedrock Server Manager API."""

    def __init__(
        self,
        host: str,
        port: int,  # Should be passed as int
        username: str,
        password: str,
        session: aiohttp.ClientSession,
        base_path: str = "/api",
    ):
        """Initialize the API client."""
        # Ensure host doesn't accidentally include schema
        host = host.replace("http://", "").replace("https://", "")
        self._base_url = f"http://{host}:{port}{base_path}"  # Construct base URL
        self._username = username
        self._password = password
        self._session = session
        self._jwt_token: Optional[str] = None
        self._headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        data: Optional[Dict[str, Any]] = None,
        authenticated: bool = True,
        is_retry: bool = False,
    ) -> Dict[str, Any]:
        """Internal method to make API requests."""
        url = f"{self._base_url}{path}"
        headers = self._headers.copy()

        if authenticated:
            if not self._jwt_token:
                _LOGGER.debug(
                    "No token found for authenticated request %s, attempting login first.",
                    path,
                )
                try:
                    await self.authenticate()
                except AuthError:
                    _LOGGER.error("Initial authentication failed for request %s", path)
                    raise  # Re-raise the AuthError
            if self._jwt_token:
                headers["Authorization"] = f"Bearer {self._jwt_token}"
                _LOGGER.debug("Added Bearer token to headers for %s", path)
            else:
                _LOGGER.error(
                    "Authentication required for %s but no token available after login attempt.",
                    path,
                )
                raise AuthError(
                    "Authentication required but no token available after login attempt."
                )

        _LOGGER.debug("Making API request: %s %s (Headers: %s)", method, url, headers)
        try:
            async with self._session.request(
                method, url, json=data, headers=headers, raise_for_status=False
            ) as response:
                _LOGGER.debug(
                    "API Raw Response Status for %s %s: %s",
                    method,
                    path,
                    response.status,
                )

                # Handle Unauthorized (Token Expired/Invalid) - Only retry once
                if response.status == 401 and authenticated and not is_retry:
                    _LOGGER.warning(
                        "Received 401 Unauthorized for %s, attempting token refresh and retry.",
                        path,
                    )
                    self._jwt_token = None  # Invalidate the current token
                    try:
                        # Retry the request *once* after forcing re-authentication
                        return await self._request(
                            method, path, data=data, authenticated=True, is_retry=True
                        )
                    except AuthError:
                        _LOGGER.error("Re-authentication failed after 401.")
                        raise  # Re-raise the AuthError from the failed authenticate() call

                # Still 401 (initial login failed, retry failed, or non-authenticated route failed auth)
                elif response.status == 401:
                    resp_text = await response.text()
                    error_message = resp_text
                    try:
                        error_data = await response.json()
                        error_message = error_data.get(
                            "message", error_data.get("error", resp_text)
                        )
                    except (aiohttp.ContentTypeError, ValueError):
                        pass
                    if (
                        path == "/login"
                        and "bad username or password" in error_message.lower()
                    ):
                        raise AuthError("Bad username or password")
                    else:
                        raise AuthError(f"Authentication Failed (401): {error_message}")

                # Handle Server Not Found (based on pre-validation or specific endpoints)
                if response.status == 404 and path.startswith("/server/"):
                    resp_text = await response.text()
                    error_message = resp_text
                    try:
                        error_data = await response.json()
                        error_message = error_data.get("message", resp_text)
                    except (aiohttp.ContentTypeError, ValueError):
                        pass
                    raise ServerNotFoundError(
                        f"Server Not Found (404): {error_message}"
                    )

                # Handle 501 Not Implemented
                if response.status == 501:
                    resp_text = await response.text()
                    error_message = resp_text
                    try:
                        error_data = await response.json()
                        error_message = error_data.get("message", resp_text)
                    except (aiohttp.ContentTypeError, ValueError):
                        pass
                    raise APIError(f"Feature Not Implemented (501): {error_message}")

                # Handle other HTTP errors (4xx Client Errors, 5xx Server Errors)
                if response.status >= 400:
                    resp_text = await response.text()
                    error_message = resp_text
                    try:
                        error_data = await response.json()
                        error_message = error_data.get("message", resp_text)
                        # Check for specific error messages indicating server not running for an action
                        msg_lower = error_message.lower()
                        if (
                            response.status == 500
                            and authenticated
                            and (
                                "is not running" in msg_lower
                                or "screen session" in msg_lower
                                and "not found" in msg_lower
                                or "pipe does not exist" in msg_lower
                                or "server likely not running" in msg_lower
                            )
                        ):
                            raise ServerNotRunningError(
                                f"Operation failed: {error_message}"
                            )
                    except (aiohttp.ContentTypeError, ValueError):
                        pass
                    raise APIError(f"API Error {response.status}: {error_message}")

                # --- Handle Success ---
                _LOGGER.debug(
                    "API request successful for %s [%s]", path, response.status
                )
                if response.status == 204:
                    return {
                        "status": "success",
                        "message": "Operation successful (No Content)",
                    }
                try:
                    json_response = await response.json()
                    # Check if the response format indicates error despite 2xx status
                    if (
                        isinstance(json_response, dict)
                        and json_response.get("status") == "error"
                    ):
                        error_message = json_response.get(
                            "message", "Unknown error structure in success response."
                        )
                        _LOGGER.error(
                            "API returned success status (%s) but error in body for %s: %s",
                            response.status,
                            path,
                            error_message,
                        )
                        if "is not running" in error_message.lower():
                            raise ServerNotRunningError(error_message)
                        else:
                            raise APIError(error_message)
                    return json_response
                except (aiohttp.ContentTypeError, ValueError):
                    resp_text = await response.text()
                    _LOGGER.warning(
                        "Successful API response (%s) for %s was not JSON: %s",
                        response.status,
                        path,
                        resp_text[:100],
                    )
                    return {
                        "status": "success",
                        "message": "Operation successful (Non-JSON response)",
                        "raw_response": resp_text,
                    }

        # Handle network/connection errors
        except aiohttp.ClientError as e:
            _LOGGER.error("API connection error for %s: %s", url, e)
            raise CannotConnectError(f"Connection Error: {e}") from e
        # Handle our own raised exceptions to ensure they propagate
        except (
            AuthError,
            ServerNotFoundError,
            ServerNotRunningError,
            APIError,
            CannotConnectError,
        ) as e:
            raise e
        # Catch any other unexpected errors during the request process
        except Exception as e:
            _LOGGER.exception("Unexpected error during API request to %s: %s", url, e)
            raise APIError(f"An unexpected error occurred during request: {e}") from e

    async def authenticate(self) -> bool:
        """Authenticate with the API and store the JWT. Raises AuthError on failure."""
        _LOGGER.info("Attempting API authentication for user %s", self._username)
        try:
            response_data = await self._request(
                "POST",
                "/login",
                data={"username": self._username, "password": self._password},
                authenticated=False,  # Login endpoint itself doesn't require prior auth
            )
            token = response_data.get("access_token")
            if not token or not isinstance(token, str):
                _LOGGER.error(
                    "Authentication successful but 'access_token' missing or invalid in response: %s",
                    response_data,
                )
                raise AuthError("Login response missing or invalid access_token.")
            _LOGGER.info("Authentication successful, token received.")
            self._jwt_token = token
            return True
        except (
            AuthError
        ) as e:  # Catch specific auth errors from _request (e.g. 401 on login)
            _LOGGER.error("Authentication failed during login attempt: %s", e)
            self._jwt_token = None
            raise
        except (
            APIError
        ) as e:  # Catch other errors during login attempt (e.g., connection refused)
            _LOGGER.error("API error during authentication: %s", e)
            self._jwt_token = None
            raise AuthError(f"API error during login: {e}") from e

    # --- Server List Method ---
    async def async_get_server_list(self) -> List[str]:
        """Fetches the list of server names from the API (GET /api/servers)."""
        _LOGGER.debug("Fetching server list from API endpoint /servers")
        try:
            response_data = await self._request("GET", "/servers", authenticated=True)
            servers_raw = response_data.get("servers")
            if not isinstance(servers_raw, list):
                raise APIError(
                    f"Invalid format for server list response: {response_data}"
                )
            server_list: List[str] = []
            for item in servers_raw:
                if (
                    isinstance(item, dict)
                    and "name" in item
                    and isinstance(item["name"], str)
                ):
                    server_list.append(item["name"])
                elif isinstance(item, str):
                    server_list.append(item)
                else:
                    _LOGGER.warning("Skipping invalid item in server list: %s", item)
            if not server_list:
                _LOGGER.warning("API returned an empty server list.")
            return sorted(server_list)
        except APIError as e:
            _LOGGER.error("API error fetching server list: %s", e)
            raise

    # --- Server Information Methods ---
    async def async_validate_server_exists(self, server_name: str) -> bool:
        """Checks if a server configuration exists via the validate endpoint."""
        _LOGGER.debug("Validating existence of server: %s", server_name)
        try:
            await self._request(
                "GET", f"/server/{server_name}/validate", authenticated=True
            )
            return True
        except ServerNotFoundError:
            _LOGGER.warning(
                "Validation failed: Server %s not found via API.", server_name
            )
            raise
        except APIError as e:
            _LOGGER.error("Error validating server %s: %s", server_name, e)
            raise

    async def async_get_server_status_info(self, server_name: str) -> Dict[str, Any]:
        """Gets runtime status info (process details, etc.) for a specific server."""
        return await self._request(
            "GET", f"/server/{server_name}/status_info", authenticated=True
        )

    async def async_get_version(self, server_name: str) -> Optional[str]:
        """Gets the configured installed version for a specific server."""
        try:
            data = await self._request(
                "GET", f"/server/{server_name}/version", authenticated=True
            )
            version = data.get("installed_version")
            return str(version) if version is not None else None
        except APIError as e:
            _LOGGER.warning("Could not fetch version for %s: %s", server_name, e)
            return None

    async def async_get_world_name(self, server_name: str) -> Optional[str]:
        """Gets the configured world name for a specific server."""
        try:
            data = await self._request(
                "GET", f"/server/{server_name}/world_name", authenticated=True
            )
            world = data.get("world_name")
            return str(world) if world is not None else None
        except APIError as e:
            _LOGGER.warning("Could not fetch world name for %s: %s", server_name, e)
            return None

    # --- Server Action Methods ---
    async def async_start_server(self, server_name: str) -> Dict[str, Any]:
        """Starts the server."""
        return await self._request(
            "POST", f"/server/{server_name}/start", authenticated=True
        )

    async def async_stop_server(self, server_name: str) -> Dict[str, Any]:
        """Stops the server."""
        return await self._request(
            "POST", f"/server/{server_name}/stop", authenticated=True
        )

    async def async_restart_server(self, server_name: str) -> Dict[str, Any]:
        """Restarts the server."""
        return await self._request(
            "POST", f"/server/{server_name}/restart", authenticated=True
        )

    async def async_send_command(
        self, server_name: str, command: str
    ) -> Dict[str, Any]:
        """Sends a command to the server. Raises ServerNotRunningError if applicable."""
        payload = {"command": command}
        return await self._request(
            "POST",
            f"/server/{server_name}/send_command",
            data=payload,
            authenticated=True,
        )

    async def async_update_server(self, server_name: str) -> Dict[str, Any]:
        """Triggers the server update process."""
        return await self._request(
            "POST", f"/server/{server_name}/update", authenticated=True
        )

    async def async_delete_server(self, server_name: str) -> Dict[str, Any]:
        """Deletes the server (Use with caution!)."""
        return await self._request(
            "DELETE", f"/server/{server_name}/delete", authenticated=True
        )

    async def async_trigger_backup(
        self,
        server_name: str,
        backup_type: str = "all",
        file_to_backup: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Triggers a backup operation (world, config, or all)."""
        _LOGGER.debug(
            "Triggering backup for server '%s', type: %s%s",
            server_name,
            backup_type,
            f", file: {file_to_backup}" if file_to_backup else "",
        )
        payload: Dict[str, str] = {"backup_type": backup_type}
        if backup_type.lower() == "config":
            if not file_to_backup:
                raise ValueError(
                    "file_to_backup is required when backup_type is 'config'"
                )
            payload["file_to_backup"] = file_to_backup
        return await self._request(
            "POST",
            f"/server/{server_name}/backup/action",
            data=payload,
            authenticated=True,
        )

    async def async_export_world(self, server_name: str) -> Dict[str, Any]:
        """Triggers world export for a server. Calls POST /api/server/{server_name}/world/export."""
        _LOGGER.debug("Triggering world export for server '%s'", server_name)
        return await self._request(
            method="POST",
            path=f"/server/{server_name}/world/export",
            data=None,  # No body needed
            authenticated=True,
        )

    async def async_prune_backups(
        self, server_name: str, keep: Optional[int] = None
    ) -> Dict[str, Any]:
        """Triggers backup pruning for a server. Calls POST /api/server/{server_name}/backups/prune."""
        _LOGGER.debug(
            "Triggering backup pruning for server '%s'%s",
            server_name,
            (
                f" (keeping {keep})"
                if keep is not None
                else " (using manager default keep)"
            ),
        )
        # Build payload ONLY if keep is specified
        payload: Optional[Dict[str, Any]] = None
        if keep is not None:
            payload = {"keep": keep}

        return await self._request(
            method="POST",
            path=f"/server/{server_name}/backups/prune",
            data=payload,  # Send None or {"keep": N}
            authenticated=True,
        )

    async def async_restore_backup(
        self, server_name: str, restore_type: str, backup_file: str
    ) -> Dict[str, Any]:
        """Restores a specific backup file. Calls POST /api/server/{server_name}/restore/action."""
        _LOGGER.debug(
            "Requesting restore for server '%s', type: %s, file: %s",
            server_name,
            restore_type,
            backup_file,
        )
        payload = {
            "restore_type": restore_type,
            "backup_file": backup_file,
        }
        return await self._request(
            method="POST",
            path=f"/server/{server_name}/restore/action",
            data=payload,
            authenticated=True,
        )

    async def async_restore_latest_all(self, server_name: str) -> Dict[str, Any]:
        """Restores the latest 'all' backup. Calls POST /api/server/{server_name}/restore/all."""
        _LOGGER.debug("Requesting restore latest all for server '%s'", server_name)
        return await self._request(
            method="POST",
            path=f"/server/{server_name}/restore/all",
            data=None,  # No body needed
            authenticated=True,
        )

    # --- Add Allowlist Methods ---
    async def async_get_allowlist(self, server_name: str) -> Dict[str, Any]:
        """Gets the current allowlist for a server. Calls GET /api/server/{server_name}/allowlist."""
        _LOGGER.debug("Fetching allowlist for server '%s'", server_name)
        return await self._request(
            method="GET", path=f"/server/{server_name}/allowlist", authenticated=True
        )

    async def async_add_to_allowlist(
        self, server_name: str, players: List[str], ignores_player_limit: bool = False
    ) -> Dict[str, Any]:
        """Adds players to the allowlist. Calls POST /api/server/{server_name}/allowlist/add."""
        _LOGGER.debug(
            "Adding players %s to allowlist for server '%s'", players, server_name
        )
        payload = {
            "players": players,
            "ignoresPlayerLimit": ignores_player_limit,
        }
        return await self._request(
            method="POST",
            path=f"/server/{server_name}/allowlist/add",
            data=payload,
            authenticated=True,
        )

    async def async_remove_from_allowlist(
        self, server_name: str, player_name: str
    ) -> Dict[str, Any]:
        """Removes a player from the allowlist. Calls DELETE /api/server/{server_name}/allowlist/player/{player_name}."""
        _LOGGER.debug(
            "Removing player '%s' from allowlist for server '%s'",
            player_name,
            server_name,
        )
        # Player name goes in the path, needs URL encoding if it contains special chars (aiohttp usually handles this)
        return await self._request(
            method="DELETE",
            path=f"/server/{server_name}/allowlist/player/{player_name}",
            data=None,  # No body
            authenticated=True,
        )

    # --- Global Manager Action Methods ---
    async def async_scan_player_logs(self) -> Dict[str, Any]:
        """Triggers scanning of player logs."""
        # Calls POST /api/players/scan
        _LOGGER.debug("Triggering player log scan")
        return await self._request("POST", "/players/scan", authenticated=True)

    async def async_prune_download_cache(
        self, directory: str, keep: Optional[int] = None
    ) -> Dict[str, Any]:
        """Triggers pruning of the global download cache for a specific directory.
        Calls POST /api/downloads/prune.
        """
        _LOGGER.debug(
            "Triggering download cache prune via API for directory '%s'%s",
            directory,
            (
                f" (keeping {keep})"
                if keep is not None
                else " (using manager default keep)"
            ),
        )

        # Build payload - directory is required
        payload: Dict[str, Any] = {"directory": directory}
        if keep is not None:
            payload["keep"] = keep  # Add keep only if provided

        return await self._request(
            method="POST",
            path="/downloads/prune",
            data=payload,  # Send the required payload
            authenticated=True,
        )

    async def async_install_server(
        self, server_name: str, server_version: str, overwrite: bool = False
    ) -> Dict[str, Any]:
        """Requests installation of a new server instance. Calls POST /api/server/install."""
        _LOGGER.info(
            "Requesting install for server '%s', version: %s, overwrite: %s",
            server_name,
            server_version,
            overwrite,
        )
        payload = {
            "server_name": server_name,
            "server_version": server_version,
            "overwrite": overwrite,  # Pass the overwrite flag
        }
        return await self._request(
            method="POST",
            path="/server/install",  # Global endpoint
            data=payload,
            authenticated=True,
        )

    async def async_delete_server(self, server_name: str) -> Dict[str, Any]:
        """Deletes the server. Calls DELETE /api/server/{server_name}/delete. USE WITH CAUTION!"""
        _LOGGER.warning(
            "Requesting deletion of server '%s'. This is irreversible.", server_name
        )
        # DELETE request, no body needed
        return await self._request(
            method="DELETE",
            path=f"/server/{server_name}/delete",
            data=None,  # No body
            authenticated=True,
        )
