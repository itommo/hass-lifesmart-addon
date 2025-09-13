from __future__ import annotations
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)

try:
    from .climate_airboard import async_setup_entry as _airboard_setup_entry
except Exception as exc:
    _LOGGER.error("lifesmart.climate: climate_airboard import failed: %s", exc)
    _airboard_setup_entry = None

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    if _airboard_setup_entry is None:
        _LOGGER.error("lifesmart.climate: no climate_airboard; nothing to set up")
        return
    _LOGGER.info("lifesmart.climate: delegating to climate_airboard")
    await _airboard_setup_entry(hass, entry, async_add_entities)
