from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.core import callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
REGIONS = ["cn", "us", "eu", "sg"]

class LifeSmartConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    _mode: Optional[str] = None

    async def async_step_user(self, user_input: Dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._mode = user_input["mode"]
            return await (self.async_step_cloud() if self._mode == "cloud" else self.async_step_local())
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        schema = vol.Schema({vol.Required("mode", default="cloud"): vol.In(["cloud", "local"]) })
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_import(self, user_input: Dict[str, Any]) -> FlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return self.async_create_entry(title="LifeSmart (import)", data=user_input or {})

    async def async_step_cloud(self, user_input: Dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            data = {"mode": "cloud", **user_input}
            return await self._create_singleton("LifeSmart (Cloud)", data)
        schema = vol.Schema({
            vol.Required("region", default="sg"): vol.In(REGIONS),
            vol.Required("app_key"): str,
            vol.Required("token"): str,
            vol.Required("user_id"): str,
            vol.Optional("password"): str,
        })
        return self.async_show_form(step_id="cloud", data_schema=schema)

    async def async_step_local(self, user_input: Dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            data = {"mode": "local", **user_input}
            return await self._create_singleton("LifeSmart (Local)", data)
        schema = vol.Schema({
            vol.Required("host"): str,
            vol.Optional("port", default=8888): int,
            vol.Required("username"): str,
            vol.Required("password"): str,
        })
        return self.async_show_form(step_id="local", data_schema=schema)

    async def _create_singleton(self, title: str, data: Dict[str, Any]) -> FlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return self.async_create_entry(title=title, data=data)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return LifeSmartOptionsFlow(config_entry)

class LifeSmartOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self.entry = entry

    async def async_step_init(self, user_input: Dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        default_exclude_devices = self.entry.options.get("exclude_devices", "")
        default_exclude_hubs = self.entry.options.get("exclude_hubs", "")
        default_inject_dummy = bool(self.entry.options.get("inject_dummy", False))

        schema = vol.Schema({
            vol.Optional("exclude_devices", default=default_exclude_devices): str,
            vol.Optional("exclude_hubs", default=default_exclude_hubs): str,
            vol.Optional("inject_dummy", default=default_inject_dummy): bool,
        })
        return self.async_show_form(step_id="init", data_schema=schema)
