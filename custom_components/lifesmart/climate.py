"""Support for LifeSmart climate devices (VRV/thermostat).

Adds modern Home Assistant ConfigEntry setup (async_setup_entry) and keeps a legacy
async_setup_platform for compatibility. For VRV, we delegate to climate_airboard.py
which you already have in this integration.
"""
from __future__ import annotations
import logging
import time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.components.climate import ENTITY_ID_FORMAT, ClimateEntity
from homeassistant.components.climate.const import (
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import PRECISION_WHOLE, UnitOfTemperature

# Base class provided by your integration
from . import LifeSmartDevice  # type: ignore

_LOGGER = logging.getLogger(__name__)

# --------------------
# Modern HA entry point
# --------------------
try:
    # Your repo already contains the real implementation here.
    from .climate_airboard import async_setup_entry as _airboard_setup_entry  # type: ignore
except Exception as exc:  # pragma: no cover
    _LOGGER.error("lifesmart.climate: failed to import climate_airboard: %s", exc)
    _airboard_setup_entry = None

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """ConfigEntry setup: delegate to climate_airboard if present."""
    if _airboard_setup_entry is None:
        _LOGGER.error("lifesmart.climate: climate_airboard not available; cannot set up climate")
        return
    _LOGGER.debug("lifesmart.climate: delegating to climate_airboard from %s", __file__)
    await _airboard_setup_entry(hass, entry, async_add_entities)

# -----------------------------------------
# Legacy platform setup (kept for compatibility only)
# -----------------------------------------
LIFESMART_STATE_LIST = [
    HVACMode.OFF, HVACMode.AUTO, HVACMode.FAN_ONLY, HVACMode.COOL, HVACMode.HEAT, HVACMode.DRY
]
LIFESMART_STATE_LIST2 = [HVACMode.OFF, HVACMode.HEAT]
FAN_MODES = [FAN_LOW, FAN_MEDIUM, FAN_HIGH]
GET_FAN_SPEED = {FAN_LOW: 15, FAN_MEDIUM: 45, FAN_HIGH: 76}
AIR_TYPES = ["V_AIR_P"]
THER_TYPES = ["SL_CP_DN"]

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Legacy setup for older flows (safe to keep)."""
    if discovery_info is None:
        return
    dev = discovery_info.get("dev")
    param = discovery_info.get("param")
    if not dev:
        return
    cdata = dev.get("data", {})
    if "T" not in cdata and "P3" not in cdata:
        return
    entities: list[LifeSmartClimateDevice] = [LifeSmartClimateDevice(dev, "idx", "0", param)]
    async_add_entities(entities)

class LifeSmartClimateDevice(LifeSmartDevice, ClimateEntity):
    """Legacy LifeSmart climate entity (compatibility path)."""

    def __init__(self, dev, idx, val, param):
        super().__init__(dev, idx, val, param)
        self._name = dev["name"]
        self._devtype = dev.get("devtype")
        cdata = dev.get("data", {})
        self.entity_id = ENTITY_ID_FORMAT.format(
            (dev["devtype"] + "_" + dev["agt"][:-3] + "_" + dev["me"])
            .lower()
            .replace(":", "_")
            .replace("@", "_")
        )
        # safe defaults
        self._attributes = getattr(self, "_attributes", {})
        self._current_temperature = None
        self._target_temperature = None
        self._min_temp = 5
        self._max_temp = 35
        self._fanspeed = 0

        if self._devtype in AIR_TYPES:
            self._modes = LIFESMART_STATE_LIST
            if cdata.get("O", {}).get("type", 0) % 2 == 0:
                self._mode = LIFESMART_STATE_LIST[0]
            else:
                self._mode = LIFESMART_STATE_LIST[cdata.get("MODE", {}).get("val", 0)]
            self._attributes.update({"last_mode": self._mode})
            self._current_temperature = cdata.get("T", {}).get("v")
            self._target_temperature = cdata.get("tT", {}).get("v")
            self._min_temp = 10
            self._max_temp = 35
            self._fanspeed = cdata.get("F", {}).get("val", 0)
        else:
            self._modes = LIFESMART_STATE_LIST2
            if cdata.get("P1", {}).get("type", 0) % 2 == 0:
                self._mode = LIFESMART_STATE_LIST2[0]
            else:
                self._mode = LIFESMART_STATE_LIST2[1]
            self._attributes.setdefault("Heating", "true" if cdata.get("P2", {}).get("type", 0) % 2 else "false")
            self._current_temperature = (cdata.get("P4", {}).get("val", 0)) / 10
            self._target_temperature = (cdata.get("P3", {}).get("val", 0)) / 10

    # ---- HA properties
    @property
    def unique_id(self): return self.entity_id
    @property
    def precision(self): return PRECISION_WHOLE
    @property
    def temperature_unit(self): return UnitOfTemperature.CELSIUS
    @property
    def target_temperature_step(self): return 1

    @property
    def fan_mode(self):
        spd = int(self._fanspeed or 0)
        if spd < 30: return FAN_LOW
        if spd < 65: return FAN_MEDIUM
        return FAN_HIGH

    @property
    def fan_modes(self): return [FAN_LOW, FAN_MEDIUM, FAN_HIGH]

    async def async_set_temperature(self, **kwargs: Any):
        new_temp = int(float(kwargs["temperature"]) * 10)
        _LOGGER.debug("set_temperature: %s", new_temp)
        if self._devtype in AIR_TYPES:
            await super().async_lifesmart_epset("0x88", new_temp, "tT")
        else:
            await super().async_lifesmart_epset("0x88", new_temp, "P3")

    async def async_set_fan_mode(self, fan_mode):
        await super().async_lifesmart_epset("0xCE", GET_FAN_SPEED[fan_mode], "F")

    async def async_set_hvac_mode(self, hvac_mode):
        if self._devtype in AIR_TYPES:
            if hvac_mode == HVACMode.OFF:
                await super().async_lifesmart_epset("0x80", 0, "O")
                return
            if getattr(self, "_mode", HVACMode.OFF) == HVACMode.OFF:
                if await super().async_lifesmart_epset("0x81", 1, "O") == 0:
                    time.sleep(2)
                else:
                    return
            await super().async_lifesmart_epset("0xCE", LIFESMART_STATE_LIST.index(hvac_mode), "MODE")
        elif hvac_mode == HVACMode.OFF:
            await super().async_lifesmart_epset("0x80", 0, "P1")
            time.sleep(1)
            await super().async_lifesmart_epset("0x80", 0, "P2")
        else:
            if await super().async_lifesmart_epset("0x81", 1, "P1") == 0:
                time.sleep(2)
