"""LifeSmart integration bootstrap.

- Proper ConfigEntry setup & unload
- Forwards platforms including `climate`
- Shared data store at hass.data[DOMAIN][entry_id]
- Safe websocket/dispatcher bridge to platform entities
- YAML import support (imports `lifesmart:` from configuration.yaml into a ConfigEntry)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from . import const as LS  # DOMAIN + keys used across the integration
from .const import DOMAIN  # convenience alias

_LOGGER = logging.getLogger(__name__)

# All platforms we support (these modules must exist in custom_components/lifesmart/)
PLATFORMS: list[str] = ["binary_sensor", "sensor", "switch", "light", "cover", "climate"]

# --------------------------
# Helpers used across modules
# --------------------------
def _slug(s: Any) -> str:
    return str(s).lower().replace(":", "_").replace("@", "_")

def generate_entity_id(device_type: Any, hub_id: Any, device_id: Any, sub_key: Any) -> str:
    """Public helper: platforms import this function via `from . import generate_entity_id`."""
    return f"{_slug(device_type)}_{_slug(hub_id)}_{_slug(device_id)}_{_slug(sub_key)}"

# --------------- HA entrypoints ---------------

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """YAML setup: import into a ConfigEntry if `lifesmart:` is present."""
    if DOMAIN in config:
        data = config.get(DOMAIN) or {}
        _LOGGER.debug("LifeSmart: importing YAML configuration into a ConfigEntry")
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=data
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LifeSmart from a config entry."""
    _LOGGER.debug("Setting up LifeSmart entry %s", entry.entry_id)

    # Build/refresh our per-entry store
    store: Dict[str, Any] = hass.data.setdefault(DOMAIN, {}).get(entry.entry_id, {})

    # Options (strings or lists accepted)
    exclude_devices = entry.options.get("exclude_devices", [])
    if isinstance(exclude_devices, str):
        exclude_devices = [x.strip() for x in exclude_devices.split(",") if x.strip()]
    exclude_hubs = entry.options.get("exclude_hubs", [])
    if isinstance(exclude_hubs, str):
        exclude_hubs = [x.strip() for x in exclude_hubs.split(",") if x.strip()]

    client = store.get("client")
    if client is None:
        client = await _maybe_create_client(hass, entry)
        if client is None:
            _LOGGER.warning("LifeSmart: client not created; continuing (platforms will still load)")

    devices = store.get("devices")
    if devices is None:
        devices = await _maybe_fetch_devices(client) or []

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "devices": devices,
        "exclude_devices": exclude_devices,
        "exclude_hubs": exclude_hubs,
    }

    _attach_ws_listener_if_possible(hass, entry, client)

    # Forward all platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug("LifeSmart entry %s setup complete", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload LifeSmart config entry."""
    _LOGGER.debug("Unloading LifeSmart entry %s", entry.entry_id)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    store = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if store:
        client = store.get("client")
        _detach_ws_listener_if_possible(client)
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN, None)

    return unload_ok


# --------------- Client helpers ---------------

async def _maybe_create_client(hass: HomeAssistant, entry: ConfigEntry):
    """Create LifeSmart client using common patterns; tolerate missing client module."""
    data = entry.data or {}
    try:
        # Pattern A: async factory
        from .client import async_create_client  # type: ignore[attr-defined]
        client = await async_create_client(hass, data, entry.options)
        _LOGGER.debug("LifeSmart: created client via async_create_client()")
        return client
    except Exception as exc:
        _LOGGER.debug("LifeSmart: async_create_client not available (%s)", exc)

    try:
        # Pattern B: class with optional async_connect
        from .client import LifeSmartClient  # type: ignore[attr-defined]
        client = LifeSmartClient(hass, data, entry.options)  # type: ignore[call-arg]
        if hasattr(client, "async_connect"):
            await client.async_connect()  # type: ignore[attr-defined]
        _LOGGER.debug("LifeSmart: created client via LifeSmartClient()")
        return client
    except Exception as exc:
        _LOGGER.debug("LifeSmart: LifeSmartClient not available (%s)", exc)
    return None


async def _maybe_fetch_devices(client) -> Optional[list]:
    """Try several method names to fetch devices."""
    if client is None:
        return None
    for attr in ("async_get_devices", "async_list_devices", "get_devices"):
        if hasattr(client, attr):
            try:
                res = getattr(client, attr)()
                if hasattr(res, "__await__"):
                    res = await res
                if isinstance(res, list):
                    return res
            except Exception as exc:
                _LOGGER.debug("LifeSmart: device fetch via %s failed: %s", attr, exc)
    return None


# --------------- Websocket bridge ---------------

def _attach_ws_listener_if_possible(hass: HomeAssistant, entry: ConfigEntry, client) -> None:
    """Attach a websocket/message listener if the client exposes one."""
    if client is None:
        return

    @callback
    def _on_message(msg: Dict[str, Any]) -> None:
        """Bridge client message to the matching entity via dispatcher, safely."""
        try:
            device_type = msg.get(LS.DEVICE_TYPE_KEY)
            hub_id = msg.get(LS.HUB_ID_KEY)
            device_id = msg.get(LS.DEVICE_ID_KEY)
            sub_key = msg.get(LS.SUBDEVICE_INDEX_KEY)

            if not all([device_type, hub_id, device_id, sub_key]):
                _LOGGER.debug("lifesmart: message missing keys, dropping: %s", msg)
                return

            entity_id = generate_entity_id(device_type, hub_id, device_id, sub_key)

            # If the entity isn't created/enabled yet, drop the update quietly
            if hass.states.get(entity_id) is None:
                _LOGGER.debug("lifesmart: dropping update for unknown/disabled entity %s", entity_id)
                return

            # Fan out to the entity via dispatcher
            async_dispatcher_send(
                hass,
                f"{LS.LIFESMART_SIGNAL_UPDATE_ENTITY}_{entity_id}",
                msg,
            )
        except Exception as exc:
            _LOGGER.exception("lifesmart: exception in websocket handler: %s", exc)

    bound = False
    for setter in ("add_message_callback", "add_listener", "on_message", "set_message_handler"):
        if hasattr(client, setter):
            try:
                getattr(client, setter)(_on_message)  # type: ignore[misc]
                setattr(client, "_lifesmart_ws_cb", _on_message)
                bound = True
                _LOGGER.debug("LifeSmart: websocket listener attached via %s()", setter)
                break
            except Exception as exc:
                _LOGGER.debug("LifeSmart: failed attaching via %s(): %s", setter, exc)
    if not bound:
        _LOGGER.debug("LifeSmart: client has no websocket callback registration; continuing without it")


def _detach_ws_listener_if_possible(client) -> None:
    """Detach previously attached listener."""
    if client is None:
        return
    cb = getattr(client, "_lifesmart_ws_cb", None)
    if cb is None:
        return
    for remover in ("remove_message_callback", "remove_listener", "off_message", "clear_message_handler"):
        if hasattr(client, remover):
            try:
                getattr(client, remover)(cb)  # type: ignore[misc]
                _LOGGER.debug("LifeSmart: websocket listener detached via %s()", remover)
                break
            except Exception:
                continue
    try:
        delattr(client, "_lifesmart_ws_cb")
    except Exception:
        pass
