"""LifeSmart integration bootstrap (Plus VRV)."""
from __future__ import annotations

import importlib
import importlib.util
import logging
from typing import Any, Dict, List, Optional

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN
from .device import LifeSmartDevice, generate_entity_id  # re-export for legacy imports

_LOGGER = logging.getLogger(__name__)

POTENTIAL_PLATFORMS: List[str] = ["binary_sensor", "sensor", "switch", "light", "cover", "climate"]

def _available_platforms() -> List[str]:
    """Forward only platforms that exist and implement async_setup_entry."""
    present: List[str] = []
    for p in POTENTIAL_PLATFORMS:
        spec = importlib.util.find_spec(f"custom_components.lifesmart.{p}")
        if not spec:
            continue
        mod = importlib.import_module(f"custom_components.lifesmart.{p}")
        if hasattr(mod, "async_setup_entry"):
            present.append(p)
        else:
            _LOGGER.warning("LifeSmart: skipping '%s' (no async_setup_entry, legacy)", p)
    return present

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    if DOMAIN in config:
        data = config.get(DOMAIN) or {}
        _LOGGER.debug("LifeSmart: importing YAML into a ConfigEntry")
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=data
            )
        )
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.debug("Setting up LifeSmart entry %s", entry.entry_id)

    store: Dict[str, Any] = hass.data.setdefault(DOMAIN, {}).get(entry.entry_id, {})

    exclude_devices = entry.options.get("exclude_devices", [])
    if isinstance(exclude_devices, str):
        exclude_devices = [x.strip() for x in exclude_devices.split(",") if x.strip()]
    exclude_hubs = entry.options.get("exclude_hubs", [])
    if isinstance(exclude_hubs, str):
        exclude_hubs = [x.strip() for x in exclude_hubs.split(",") if x.strip()]
    inject_dummy = bool(entry.options.get("inject_dummy", False))

    client = store.get("client")
    if client is None:
        client = await _maybe_create_client(hass, entry)
        if client is None:
            _LOGGER.warning("LifeSmart: client not created; continuing (platforms will still load)")

    devices = store.get("devices")
    if devices is None:
        devices = await _maybe_fetch_devices(client) or []

    try:
        _LOGGER.info("LifeSmart: discovered %d devices", len(devices))
    except Exception:
        _LOGGER.info("LifeSmart: discovered <unknown> devices")
    for d in (devices or [])[:5]:
        devtype = d.get("devtype") if isinstance(d, dict) else getattr(d, "devtype", None)
        _LOGGER.info("LifeSmart: devtype=%s agt=%s me=%s name=%s",
                     devtype,
                     (d.get("agt") if isinstance(d, dict) else getattr(d, "agt", None)),
                     (d.get("me") if isinstance(d, dict) else getattr(d, "me", None)),
                     (d.get("name") if isinstance(d, dict) else getattr(d, "name", None)))

    if not devices and inject_dummy:
        _LOGGER.warning("LifeSmart: inject_dummy enabled; adding one SL_UACCB device for testing")
        devices = [{
            "devtype": "SL_UACCB",
            "name": "Dummy AirBoard",
            "agt": "HUB1234567890",
            "me": "DEV0001",
            "data": {
                "P1": {"type": 0x81},
                "P2": {"val": 3},
                "P3": {"val": 240},
                "P4": {"val": 45},
                "P6": {"val": 250}
            },
            "ver": "debug", "id": "DEV0001", "hub": "HUB1234567890"
        }]

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "devices": devices,
        "exclude_devices": exclude_devices,
        "exclude_hubs": exclude_hubs,
    }

    _attach_ws_listener_if_possible(hass, entry, client)

    present = _available_platforms()
    if present:
        await hass.config_entries.async_forward_entry_setups(entry, present)
        _LOGGER.debug("LifeSmart: forwarded platforms: %s", present)
    else:
        _LOGGER.warning("LifeSmart: no platform modules found to set up")
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    present = _available_platforms()
    ok = await hass.config_entries.async_unload_platforms(entry, present)
    store = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if store:
        client = store.get("client")
        _detach_ws_listener_if_possible(client)
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN, None)
    return ok

async def _maybe_create_client(hass: HomeAssistant, entry: ConfigEntry):
    data = entry.data or {}
    try:
        from .client import async_create_client
        client = await async_create_client(hass, data, entry.options)
        _LOGGER.debug("LifeSmart: created client via async_create_client()")
        return client
    except Exception as exc:
        _LOGGER.debug("LifeSmart: async_create_client not available (%s)", exc)
    try:
        from .client import LifeSmartClient
        client = LifeSmartClient(hass, data, entry.options)  # type: ignore[call-arg]
        if hasattr(client, "async_connect"):  # type: ignore[attr-defined]
            await client.async_connect()       # type: ignore[attr-defined]
        _LOGGER.debug("LifeSmart: created client via LifeSmartClient()")
        return client
    except Exception as exc:
        _LOGGER.debug("LifeSmart: LifeSmartClient not available (%s)", exc)
    return None

async def _maybe_fetch_devices(client) -> Optional[list]:
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

def _attach_ws_listener_if_possible(hass: HomeAssistant, entry: ConfigEntry, client) -> None:
    if client is None:
        return

    @callback
    def _on_message(msg: Dict[str, Any]) -> None:
        try:
            from . import const as LS
            device_type = msg.get(getattr(LS, "DEVICE_TYPE_KEY", "devtype"))
            hub_id = msg.get(getattr(LS, "HUB_ID_KEY", "agt"))
            device_id = msg.get(getattr(LS, "DEVICE_ID_KEY", "me"))
            sub_key = msg.get(getattr(LS, "SUBDEVICE_INDEX_KEY", "idx"))
            if not all([device_type, hub_id, device_id, sub_key]):
                _LOGGER.debug("lifesmart: message missing keys, dropping: %s", msg); return
            entity_id = generate_entity_id(device_type, hub_id, device_id, sub_key)
            if hass.states.get(entity_id) is None:
                _LOGGER.debug("lifesmart: dropping update for unknown/disabled entity %s", entity_id); return
            signal = getattr(LS, "LIFESMART_SIGNAL_UPDATE_ENTITY", "lifesmart_signal_update_entity")
            async_dispatcher_send(hass, f"{signal}_{entity_id}", msg)
        except Exception as exc:
            _LOGGER.exception("lifesmart: exception in websocket handler: %s", exc)

    for setter in ("add_message_callback", "add_listener", "on_message", "set_message_handler"):
        if hasattr(client, setter):
            try:
                getattr(client, setter)(_on_message)  # type: ignore[misc]
                setattr(client, "_lifesmart_ws_cb", _on_message)
                break
            except Exception as exc:
                _LOGGER.debug("LifeSmart: failed attaching via %s(): %s", setter, exc)

def _detach_ws_listener_if_possible(client) -> None:
    if client is None: return
    cb = getattr(client, "_lifesmart_ws_cb", None)
    if cb is None: return
    for remover in ("remove_message_callback", "remove_listener", "off_message", "clear_message_handler"):
        if hasattr(client, remover):
            try:
                getattr(client, remover)(cb)  # type: ignore[misc]
                break
            except Exception:
                continue
    try: delattr(client, "_lifesmart_ws_cb")
    except Exception: pass
