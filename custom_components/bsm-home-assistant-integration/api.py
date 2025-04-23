"""API Client for the Minecraft Bedrock Server Manager."""

import aiohttp
import logging
from typing import Any, Dict, Optional, List

_LOGGER = logging.getLogger(__name__)

# Define custom exceptions based on potential API/Network issues
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


class MinecraftBedrockApi:
    """Class to communicate with the Minecraft Bedrock Server Manager API."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
        base_path: str = "/api"
    ):
        """Initialize the API client."""
        self._base_url = f"http://{host}:{port}{base_path}"
        self._username = username
        self._password = password
        self._session = session
        self._jwt_token: Optional[str] = None
        self._headers = {"Accept": "application/json", "Content-Type": "application/json"}

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
                _LOGGER.debug("No token found for authenticated request, attempting login first.")
                # Use internal authenticate method which raises AuthError on failure
                await self.authenticate()

            # Check again after potential authenticate() call
            if self._jwt_token:
                 headers["Authorization"] = f"Bearer {self._jwt_token}"
            else:
                 # Should not happen if authenticate() succeeded, but handle defensively
                 raise AuthError("Authentication required but no token available after login attempt.")

        _LOGGER.debug("Making API request: %s %s (Auth=%s)", method, url, authenticated)
        try:
            async with self._session.request(
                method, url, json=data, headers=headers, raise_for_status=False # Handle status manually
            ) as response:
                _LOGGER.debug("API Raw Response Status for %s %s: %s", method, path, response.status)

                # --- Specific Error Handling ---

                # Handle Unauthorized (Token Expired/Invalid) - Only retry once
                if response.status == 401 and authenticated and not is_retry:
                    _LOGGER.warning("Received 401 Unauthorized for %s, attempting token refresh and retry.", path)
                    self._jwt_token = None # Invalidate the current token
                    try:
                        # Retry the request *once* after forcing re-authentication
                        return await self._request(method, path, data=data, authenticated=True, is_retry=True)
                    except AuthError:
                        # If the re-authentication itself fails, raise that AuthError
                        _LOGGER.error("Re-authentication failed after 401.")
                        raise # Re-raise the AuthError from the failed authenticate() call

                # If it's still 401 (either not authenticated route, retry failed, or initial login failed)
                elif response.status == 401:
                    resp_text = await response.text()
                    _LOGGER.error("Authentication failed (401) for %s: %s", path, resp_text)
                    # Try to parse JSON error message, default to text if fails
                    error_message = resp_text
                    try:
                        error_data = await response.json()
                        error_message = error_data.get('message', error_data.get('error', resp_text))
                    except (aiohttp.ContentTypeError, ValueError):
                        pass # Keep the raw text
                    # Use specific message for login endpoint based on docs
                    if path == "/login" and "bad username or password" in error_message.lower():
                         raise AuthError("Bad username or password")
                    else:
                         raise AuthError(f"Authentication Failed (401): {error_message}")

                # Handle Server Not Found (based on pre-validation or specific endpoints)
                # Check common path structure and 404 status
                if response.status == 404 and path.startswith("/server/"):
                     resp_text = await response.text()
                     _LOGGER.warning("Received 404 Not Found for server path: %s", path)
                     error_message = resp_text
                     try:
                          error_data = await response.json()
                          error_message = error_data.get('message', resp_text)
                     except (aiohttp.ContentTypeError, ValueError):
                          pass
                     raise ServerNotFoundError(f"Server Not Found (404): {error_message}")

                # Handle 501 Not Implemented
                if response.status == 501:
                    resp_text = await response.text()
                    _LOGGER.warning("Received 501 Not Implemented for %s: %s", path, resp_text)
                    error_message = resp_text
                    try:
                        error_data = await response.json()
                        error_message = error_data.get('message', resp_text)
                    except (aiohttp.ContentTypeError, ValueError):
                          pass
                    raise APIError(f"Feature Not Implemented (501): {error_message}") # General APIError for 501

                # Handle other HTTP errors (4xx Client Errors, 5xx Server Errors)
                if response.status >= 400:
                    resp_text = await response.text()
                    _LOGGER.error("API request failed for %s [%s]: %s", path, response.status, resp_text)
                    error_message = resp_text
                    try:
                        error_data = await response.json()
                        error_message = error_data.get('message', resp_text)
                        # Check for specific error messages indicating server not running for an action
                        msg_lower = error_message.lower()
                        if response.status == 500 and (
                             "is not running" in msg_lower
                             or "screen session" in msg_lower and "not found" in msg_lower
                             or "pipe does not exist" in msg_lower
                             or "server likely not running" in msg_lower
                        ):
                            raise ServerNotRunningError(f"Operation failed: {error_message}")

                    except (aiohttp.ContentTypeError, ValueError):
                         pass # Keep raw text if not JSON
                    # Raise a general APIError for other 4xx/5xx errors
                    raise APIError(f"API Error {response.status}: {error_message}")


                # --- Handle Success ---
                _LOGGER.debug("API request successful for %s [%s]", path, response.status)

                # Handle potential empty success bodies (e.g., 204 No Content, common for DELETE)
                if response.status == 204:
                    return {"status": "success", "message": "Operation successful (No Content)"}

                # Try to parse JSON response for other success codes (200, 201)
                try:
                    json_response = await response.json()
                    # Check if the response format contains a standard 'status' key
                    if isinstance(json_response, dict) and json_response.get("status") == "error":
                        # Handle cases where API returns 200 OK but indicates error in body
                        error_message = json_response.get("message", "Unknown error structure in success response.")
                        _LOGGER.error("API returned success status (%s) but error in body for %s: %s", response.status, path, error_message)
                        # Should we map this to a specific error? Maybe ServerNotRunningError?
                        if "is not running" in error_message.lower():
                            raise ServerNotRunningError(error_message)
                        else:
                            raise APIError(error_message)
                    return json_response

                except (aiohttp.ContentTypeError, ValueError):
                    # Handle cases where response isn't JSON despite success code
                    resp_text = await response.text()
                    _LOGGER.warning("Successful API response (%s) for %s was not JSON: %s", response.status, path, resp_text[:100])
                    # Return a standard success dict, maybe include the text?
                    return {"status": "success", "message": "Operation successful (Non-JSON response)", "raw_response": resp_text}

        # Handle network/connection errors
        except aiohttp.ClientError as e:
            _LOGGER.error("API connection error for %s: %s", url, e)
            raise CannotConnectError(f"Connection Error: {e}") from e
        # Handle our own raised exceptions to ensure they propagate
        except (AuthError, ServerNotFoundError, ServerNotRunningError, APIError, CannotConnectError) as e:
            raise e
        # Catch any other unexpected errors during the request process
        except Exception as e:
            _LOGGER.exception("Unexpected error during API request to %s: %s", url, e)
            raise APIError(f"An unexpected error occurred during request: {e}") from e


    async def authenticate(self) -> bool:
        """Authenticate with the API and store the JWT. Raises AuthError on failure."""
        _LOGGER.info("Attempting API authentication for user %s", self._username)
        try:
            # Make the login request - deliberately don't use 'authenticated=True' here
            response_data = await self._request(
                "POST",
                "/login",
                data={"username": self._username, "password": self._password},
                authenticated=False, # Login endpoint itself doesn't require prior auth
            )
            token = response_data.get("access_token")
            if not token or not isinstance(token, str):
                _LOGGER.error("Authentication successful but 'access_token' missing or invalid in response: %s", response_data)
                raise AuthError("Login response missing or invalid access_token.")

            _LOGGER.info("Authentication successful, token received.")
            self._jwt_token = token
            return True
        except AuthError as e: # Catch specific auth errors from _request (e.g. 401 on login)
            _LOGGER.error("Authentication failed during login attempt: %s", e)
            self._jwt_token = None
            raise # Re-raise the specific AuthError
        except APIError as e: # Catch other errors during login attempt (e.g., connection refused)
            _LOGGER.error("API error during authentication: %s", e)
            self._jwt_token = None
            # Wrap it in AuthError to signify login process failure clearly
            raise AuthError(f"API error during login: {e}") from e

    # --- Server List Method ---
    async def async_get_server_list(self) -> List[str]:
        """Fetches the list of server names from the API. Assumes GET /api/servers endpoint."""
        _LOGGER.debug("Fetching server list from API endpoint /servers")
        try:
            # Assuming GET /servers requires authentication
            response_data = await self._request("GET", "/servers", authenticated=True)

            servers_raw = response_data.get("servers")
            if not isinstance(servers_raw, list):
                _LOGGER.error("Invalid format for server list response: 'servers' key not found or not a list. Response: %s", response_data)
                raise APIError("Received invalid server list format from manager.")

            server_list: List[str] = []
            for item in servers_raw:
                if isinstance(item, dict) and "name" in item and isinstance(item["name"], str):
                    server_list.append(item["name"])
                elif isinstance(item, str):
                    server_list.append(item)
                else:
                    _LOGGER.warning("Skipping invalid item in server list: %s", item)

            if not server_list:
                _LOGGER.warning("API returned an empty server list.")
                return []

            _LOGGER.debug("Successfully fetched server list: %s", server_list)
            return sorted(server_list)

        except APIError as e:
             # Catch specific errors like AuthError, CannotConnectError etc. if needed
             _LOGGER.error("API error fetching server list: %s", e)
             raise # Re-raise the original APIError (or specific subtype)

    # --- Server Information Methods ---
    async def async_validate_server_exists(self, server_name: str) -> bool:
        """Checks if a server configuration exists via the validate endpoint."""
        _LOGGER.debug("Validating existence of server: %s", server_name)
        try:
            # The validate endpoint returns 200 OK on success, raises ServerNotFoundError on 404
            await self._request("GET", f"/server/{server_name}/validate", authenticated=True)
            _LOGGER.debug("Validation successful for server: %s", server_name)
            return True
        except ServerNotFoundError:
            _LOGGER.warning("Validation failed: Server %s not found via API.", server_name)
            raise # Re-raise ServerNotFoundError for config flow to catch
        except APIError as e:
             _LOGGER.error("Error validating server %s: %s", server_name, e)
             raise # Re-raise other API errors

    async def async_get_server_status_info(self, server_name: str) -> Dict[str, Any]:
        """Gets runtime status info (process details, etc.) for a specific server."""
        # Returns dict like {"status": "success", "process_info": {...}} or {"status": "success", "process_info": null, ...}
        return await self._request("GET", f"/server/{server_name}/status_info", authenticated=True)

    async def async_get_version(self, server_name: str) -> Optional[str]:
        """Gets the configured installed version for a specific server."""
        try:
            data = await self._request("GET", f"/server/{server_name}/version", authenticated=True)
            # Ensure the key exists and the value is a string
            version = data.get("installed_version")
            return str(version) if version is not None else None
        except APIError as e:
            _LOGGER.warning("Could not fetch version for %s: %s", server_name, e)
            return None # Return None on error

    async def async_get_world_name(self, server_name: str) -> Optional[str]:
        """Gets the configured world name for a specific server."""
        try:
            data = await self._request("GET", f"/server/{server_name}/world_name", authenticated=True)
            world = data.get("world_name")
            return str(world) if world is not None else None
        except APIError as e:
            _LOGGER.warning("Could not fetch world name for %s: %s", server_name, e)
            return None

    # --- Server Action Methods ---
    async def async_start_server(self, server_name: str) -> Dict[str, Any]:
        """Starts the server."""
        return await self._request("POST", f"/server/{server_name}/start", authenticated=True)

    async def async_stop_server(self, server_name: str) -> Dict[str, Any]:
        """Stops the server."""
        return await self._request("POST", f"/server/{server_name}/stop", authenticated=True)

    async def async_restart_server(self, server_name: str) -> Dict[str, Any]:
        """Restarts the server."""
        return await self._request("POST", f"/server/{server_name}/restart", authenticated=True)

    async def async_send_command(self, server_name: str, command: str) -> Dict[str, Any]:
        """Sends a command to the server. Raises ServerNotRunningError if applicable."""
        payload = {"command": command}
        # _request method handles raising ServerNotRunningError based on 500 responses
        return await self._request("POST", f"/server/{server_name}/send_command", data=payload, authenticated=True)

    async def async_update_server(self, server_name: str) -> Dict[str, Any]:
        """Triggers the server update process."""
        return await self._request("POST", f"/server/{server_name}/update", authenticated=True)

    async def async_delete_server(self, server_name: str) -> Dict[str, Any]:
        """Deletes the server (Use with caution!)."""
        # Returns 200 OK with JSON body on success (based on docs)
        return await self._request("DELETE", f"/server/{server_name}/delete", authenticated=True)

    # --- Backup/Restore Methods (Example) ---
    async def async_trigger_backup(
        self,
        server_name: str,
        backup_type: str = "all", # Default to "all"
        file_to_backup: Optional[str] = None
    ) -> Dict[str, Any]:
        """Triggers a backup operation (world, config, or all)."""
        _LOGGER.debug(
            "Triggering backup for server '%s', type: %s%s",
            server_name,
            backup_type,
            f", file: {file_to_backup}" if file_to_backup else ""
        )
        payload: Dict[str, str] = {"backup_type": backup_type}
        if backup_type.lower() == "config":
            if not file_to_backup:
                raise ValueError("file_to_backup is required when backup_type is 'config'")
            payload["file_to_backup"] = file_to_backup

        # Make the POST request with the JSON payload
        return await self._request(
            "POST",
            f"/server/{server_name}/backup/action",
            data=payload, # Pass the payload here
            authenticated=True
        )