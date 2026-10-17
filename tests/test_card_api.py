"""Exercise card boundaries with a small Home Assistant test double."""

import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

DOMAIN = "bedrock_server_manager"


def load_card_api():
    """Load only the transport, independently of a running HA installation."""
    modules = {}
    for name in (
        "voluptuous",
        "homeassistant",
        "homeassistant.components",
        "homeassistant.components.websocket_api",
        "homeassistant.core",
        "custom_components",
        "custom_components.bedrock_server_manager",
        "custom_components.bedrock_server_manager.const",
    ):
        modules[name] = ModuleType(name)
    vol = modules["voluptuous"]
    vol.Required = vol.Optional = lambda value: value
    vol.In = lambda value: value
    core = modules["homeassistant.core"]
    core.HomeAssistant = object
    core.callback = lambda func: func
    api = modules["homeassistant.components.websocket_api"]
    api.websocket_command = lambda schema: lambda func: func
    api.require_admin = Mock(side_effect=lambda func: func)
    api.async_register_command = Mock()
    modules["homeassistant.components"].websocket_api = api
    modules["custom_components.bedrock_server_manager.const"].DOMAIN = DOMAIN
    path = (
        Path(__file__).resolve().parents[1]
        / "custom_components/bedrock_server_manager/card_api.py"
    )
    spec = importlib.util.spec_from_file_location(
        "custom_components.bedrock_server_manager.card_api", path
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    return module, api


class CardApiTests(unittest.TestCase):
    def setUp(self):
        self.module, self.api = load_card_api()
        self.entry = SimpleNamespace(entry_id="a", title="Manager", domain=DOMAIN)
        self.coordinator = SimpleNamespace(
            last_update_success=True,
            data={"status": "success", "process_info": None, "password": "secret"},
        )
        self.hass = SimpleNamespace(
            data={
                DOMAIN: {
                    "a": {"servers": {"Survival": {"coordinator": self.coordinator}}}
                }
            },
            config_entries=SimpleNamespace(
                async_get_entry=lambda entry_id: (
                    self.entry if entry_id == "a" else None
                ),
                async_entries=lambda domain: [self.entry],
            ),
        )
        self.connection = Mock()

    def read(self, **changes):
        message = {
            "id": 1,
            "entry_id": "a",
            "operation": "get_server_process_info",
            "server_name": "Survival",
            **changes,
        }
        self.module.websocket_card_read(self.hass, self.connection, message)

    def test_commands_require_admin_and_register_once(self):
        self.assertEqual(self.api.require_admin.call_count, 2)
        self.module.async_register_card_api(self.hass)
        self.module.async_register_card_api(self.hass)
        self.assertEqual(self.api.async_register_command.call_count, 2)

    def test_selected_servers_only(self):
        self.read(server_name="Unselected")
        self.connection.send_error.assert_called_once_with(
            1, "not_found", "Server is not monitored"
        )
        self.connection.send_result.assert_not_called()

    def test_unloaded_and_foreign_entries_are_rejected(self):
        self.read(entry_id="missing")
        self.connection.send_error.assert_called_once()
        self.connection.reset_mock()
        self.entry.domain = "other_integration"
        self.read()
        self.connection.send_error.assert_called_once()

    def test_failed_snapshot_is_not_reported_as_stopped(self):
        self.coordinator.last_update_success = False
        self.read()
        self.connection.send_error.assert_called_once_with(
            1, "unavailable", "Server snapshot unavailable"
        )

    def test_stopped_snapshot_excludes_unrelated_data(self):
        self.read()
        self.connection.send_result.assert_called_once_with(
            1, {"status": "success", "process_info": None}
        )

    def test_pydantic_process_is_serialized(self):
        process = Mock()
        process.model_dump.return_value = {"pid": 42}
        self.coordinator.data["process_info"] = process
        self.read()
        process.model_dump.assert_called_once_with(mode="json")
        self.connection.send_result.assert_called_once_with(
            1, {"status": "success", "process_info": {"pid": 42}}
        )

    def test_entry_choices_exclude_credentials(self):
        self.module.websocket_card_entries(self.hass, self.connection, {"id": 1})
        self.connection.send_result.assert_called_once_with(
            1, [{"entry_id": "a", "title": "Manager"}]
        )


if __name__ == "__main__":
    unittest.main()
