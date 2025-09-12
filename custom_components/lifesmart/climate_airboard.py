
"""
LifeSmart Air Board (VRV / devtype: SL_UACCB) for the "LifeSmart by iKaew" integration.
Drop-in Home Assistant climate entity.

Place this file at:
  config/custom_components/lifesmart/climate_airboard.py

What it does:
  - Discovers Air Board devices (devtype == "SL_UACCB") from the integration's device list
  - Exposes power, hvac mode, target temperature, and fan speed
  - Writes via LifeSmart OpenAPI: EpSet (P1, P2, P3, P4)

Air Board IO map (from LifeSmart docs):
  P1 (Switch): ON => type 0x81, OFF => type 0x80
  P2 (Mode):   type 0xCE, val {1:Auto,2:Fan,3:Cool,4:Heat,5:Dry}
  P3 (Target): type 0x88, val = temperature*10  (25.0°C -> 250)
  P4 (Fan):    type 0xCE, val {15:Low,45:Medium,75:High}
  P6 (Current): read-only, val = temperature*10

Notes:
  - This file is intentionally tolerant of small differences between versions of the iKaew integration.
    It tries several common shapes for `hass.data[DOMAIN][entry.entry_id]` and several client method names.
  - If discovery doesn't find devices, see INSTRUCTIONS_IKAEW.txt for the 1-2 lines you may need to tweak.
"""
from __future__ import annotations

from typing import Any, Optional

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE

from .const import DOMAIN

LS_DEVTYPE_AIRBOARD = "SL_UACCB"

LS_MODE_TO_HA = {
    1: HVACMode.AUTO,
    2: HVACMode.FAN_ONLY,
    3: HVACMode.COOL,
    4: HVACMode.HEAT,
    5: HVACMode.DRY,
}
HA_TO_LS_MODE = {v: k for k, v in LS_MODE_TO_HA.items()}

FAN_TO_VAL = {"low": 15, "medium": 45, "high": 75}

def _fan_from_val(v: int) -> str:
    if v < 30:
        return "low"
    if v < 65:
        return "medium"
    return "high"

async def async_setup_entry(hass, entry, async_add_entities):
    # Try to obtain the integration's storage bucket (client + devices) from hass.data
    store = hass.data.get(DOMAIN, {})
    bucket = store.get(entry.entry_id) or store.get("entry") or store

    client = (
        bucket.get("client")
        or bucket.get("oapi_client")
        or bucket.get("ls_client")
        or getattr(bucket, "client", None)
    )
    devices = (
        bucket.get("devices")
        or bucket.get("entities")
        or bucket.get("device_list")
        or getattr(bucket, "devices", None)
        or []
    )

    airboards = []
    for d in devices:
        # d may be dict or object
        devtype = getattr(d, "devtype", None) or getattr(d, "type", None) or (d.get("devtype") if isinstance(d, dict) else None)
        if devtype != LS_DEVTYPE_AIRBOARD:
            continue
        agt = getattr(d, "agt", None) or (d.get("agt") if isinstance(d, dict) else None)
        me = getattr(d, "me", None) or (d.get("me") if isinstance(d, dict) else None)
        data = getattr(d, "data", None) or (d.get("data") if isinstance(d, dict) else {})
        name = getattr(d, "name", None) or (d.get("name") if isinstance(d, dict) else None) or f"AirBoard {me}"
        if agt and me:
            airboards.append(LifeSmartAirBoard(client, agt, me, name, data))

    if airboards:
        async_add_entities(airboards, update_before_add=True)

class LifeSmartAirBoard(ClimateEntity):
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.AUTO, HVACMode.COOL, HVACMode.HEAT, HVACMode.DRY, HVACMode.FAN_ONLY]
    _attr_fan_modes = ["low", "medium", "high"]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_temperature_unit = UnitOfTemperature
    _attr_min_temp = 16
    _attr_max_temp = 30
    _attr_precision = 0.5

    def __init__(self, client, agt: str, me: str, name: str, data: dict[str, Any]):
        self._client = client
        self._agt = agt
        self._me = me
        self._attr_name = name
        self._data = data or {}

    # --- helpers ---
    async def _call(self, method: str, params: dict) -> Any:
        # Preferred: a generic async call pipe if present
        if hasattr(self._client, "call"):
            return await self._client.call(method, params)
        if hasattr(self._client, "async_call"):
            return await self._client.async_call(method, params)
        # Fallbacks tailored to common iKaew client shapes
        if method == "EpSet":
            if hasattr(self._client, "ep_set"):
                return await self._client.ep_set(**params)
            if hasattr(self._client, "write_io"):
                return await self._client.write_io(params["agt"], params["me"], params["idx"], params["type"], params["val"])
        if method == "EpGet":
            if hasattr(self._client, "ep_get"):
                return await self._client.ep_get(params["agt"], params["me"])
            if hasattr(self._client, "get_device"):
                return await self._client.get_device(params["agt"], params["me"])
        return None

    def _io(self, key: str) -> dict | None:
        if isinstance(self._data, dict):
            return self._data.get(key)
        return None

    # --- entity identity ---
    @property
    def unique_id(self) -> str | None:
        return f"{self._agt}:{self._me}"

    # --- state ---
    @property
    def hvac_mode(self) -> HVACMode:
        p1 = self._io("P1") or {}
        is_on = (p1.get("type", 0) % 2 == 1)
        if not is_on:
            return HVACMode.OFF
        p2 = self._io("P2") or {}
        return LS_MODE_TO_HA.get(p2.get("val"), HVACMode.AUTO)

    @property
    def target_temperature(self) -> Optional[float]:
        p3 = self._io("P3") or {}
        if "val" in p3:
            return round(p3["val"] / 10.0, 1)
        return None

    @property
    def current_temperature(self) -> Optional[float]:
        p6 = self._io("P6") or {}
        if "val" in p6:
            return round(p6["val"] / 10.0, 1)
        return None

    @property
    def fan_mode(self) -> Optional[str]:
        p4 = self._io("P4") or {}
        v = p4.get("val")
        if v is None:
            return None
        return _fan_from_val(v)

    # --- actions ---
    async def async_turn_on(self) -> None:
        await self._call("EpSet", {"agt": self._agt, "me": self._me, "idx": "P1", "type": 0x81, "val": 1})
        self._data.setdefault("P1", {})["type"] = 0x81

    async def async_turn_off(self) -> None:
        await self._call("EpSet", {"agt": self._agt, "me": self._me, "idx": "P1", "type": 0x80, "val": 0})
        self._data.setdefault("P1", {})["type"] = 0x80

    async def async_set_hvac_mode(self, mode: HVACMode) -> None:
        if mode == HVACMode.OFF:
            return await self.async_turn_off()
        await self.async_turn_on()
        val = HA_TO_LS_MODE.get(mode, 1)
        await self._call("EpSet", {"agt": self._agt, "me": self._me, "idx": "P2", "type": 0xCE, "val": val})
        self._data.setdefault("P2", {})["val"] = val

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        val = FAN_TO_VAL[fan_mode]
        await self._call("EpSet", {"agt": self._agt, "me": self._me, "idx": "P4", "type": 0xCE, "val": val})
        self._data.setdefault("P4", {})["val"] = val

    async def async_set_temperature(self, **kwargs) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        val = int(round(float(temp) * 10))
        await self._call("EpSet", {"agt": self._agt, "me": self._me, "idx": "P3", "type": 0x88, "val": val})
        self._data.setdefault("P3", {})["val"] = val

    async def async_update(self) -> None:
        resp = await self._call("EpGet", {"agt": self._agt, "me": self._me})
        if isinstance(resp, dict):
            dev = resp.get("message") if "message" in resp else resp
            data = dev.get("data") if isinstance(dev, dict) else None
            if isinstance(data, dict):
                self._data = data
