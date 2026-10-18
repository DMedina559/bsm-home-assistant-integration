"""Validate card commands against Home Assistant's real WebSocket API."""

from types import SimpleNamespace

import probatio
import pytest
from homeassistant.exceptions import Unauthorized

from custom_components.bedrock_server_manager.card_api import websocket_card_read
from custom_components.bedrock_server_manager.const import DOMAIN


def test_card_command_accepts_supported_read():
    message = {
        "id": 1,
        "type": f"{DOMAIN}/card_read",
        "entry_id": "manager",
        "operation": "get_server_process_info",
        "server_name": "Survival",
    }
    assert websocket_card_read._ws_schema(message) == message


@pytest.mark.parametrize(
    "extra", [{"operation": "delete_server"}, {"url": "http://other-host"}]
)
def test_card_command_rejects_unsupported_requests(extra):
    with pytest.raises(probatio.Invalid):
        websocket_card_read._ws_schema(
            {
                "id": 1,
                "type": f"{DOMAIN}/card_read",
                "entry_id": "manager",
                "operation": "list_servers",
                **extra,
            }
        )


def test_card_command_requires_administrator():
    with pytest.raises(Unauthorized):
        websocket_card_read(
            None, SimpleNamespace(user=SimpleNamespace(is_admin=False)), {"id": 1}
        )
