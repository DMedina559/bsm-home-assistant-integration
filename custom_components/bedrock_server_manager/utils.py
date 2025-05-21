# custom_components/bedrock_server_manager/util.py
import logging

_LOGGER = logging.getLogger(__name__)


def sanitize_host_port_string(host_port_str: str) -> str:
    """
    Sanitizes a host:port string to ensure the port part is an integer string.
    Specifically converts "port.0" to "port" if applicable.
    Handles IPv4, IPv6 (with brackets), and hostnames.
    If sanitization fails or is not applicable, returns the original string.
    """
    if not host_port_str:
        return ""

    original_str = str(host_port_str)  # Ensure it's a string to start with

    # Handle IPv6 with brackets: [address]:port
    if original_str.startswith("[") and "]:" in original_str:
        parts = original_str.split("]:", 1)
        host_part = parts[0] + "]"  # e.g., "[::1]"
        if len(parts) > 1 and parts[1]:  # If there is a port part
            port_part_str = parts[1]
            try:
                port_as_float = float(port_part_str)
                # Check if it's effectively an integer (e.g., 123.0 or 123)
                if port_as_float == int(port_as_float):
                    port_as_int = int(port_as_float)
                    # Validate port range (optional but good practice)
                    if 1 <= port_as_int <= 65535:
                        return f"{host_part}:{port_as_int}"
                    else:
                        _LOGGER.debug(
                            "Port %s out of range (1-65535) in ID string '%s', using original.",
                            port_as_int,
                            original_str,
                        )
                # else: port has non-zero decimal (e.g. 80.5), unusual, use original
            except ValueError:
                # Port part is not a number
                _LOGGER.debug(
                    "Port part '%s' is not a valid number in ID string '%s', using original.",
                    port_part_str,
                    original_str,
                )
        # If no port part after "]:", or if port processing failed, return original
        return original_str

    # Handle IPv4 or hostname: host:port (or just host without port)
    elif ":" in original_str:
        # Split by the last colon to correctly get the port
        last_colon_idx = original_str.rfind(":")
        host_part = original_str[:last_colon_idx]
        port_part_str = original_str[last_colon_idx + 1 :]

        if not host_part:  # e.g. ":8080" - this is unusual for a host:port ID
            _LOGGER.debug(
                "Malformed host-port string '%s' (no host part), using original.",
                original_str,
            )
            return original_str

        try:
            port_as_float = float(port_part_str)
            if port_as_float == int(port_as_float):
                port_as_int = int(port_as_float)
                if 1 <= port_as_int <= 65535:
                    return f"{host_part}:{port_as_int}"
                else:
                    _LOGGER.debug(
                        "Port %s out of range (1-65535) in ID string '%s', using original.",
                        port_as_int,
                        original_str,
                    )
            # else: port has non-zero decimal, unusual, use original
        except ValueError:
            _LOGGER.debug(
                "Port part '%s' is not a valid number in ID string '%s', using original.",
                port_part_str,
                original_str,
            )
        # If port processing failed, return original
        return original_str

    # No colon found, or already processed above. Assume it's just a host or already clean.
    return original_str
