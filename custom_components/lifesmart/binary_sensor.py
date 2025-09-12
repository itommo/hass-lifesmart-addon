"""Support for LifeSmart binary sensors."""
from __future__ import annotations
import logging
from typing import Any
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from . import const as LS
from . import LifeSmartDevice, generate_entity_id

_LOGGER = logging.getLogger(__name__)

BINARY_SENSOR_TYPES = LS.BINARY_SENSOR_TYPES
DEVICE_DATA_KEY = LS.DEVICE_DATA_KEY
DEVICE_ID_KEY = LS.DEVICE_ID_KEY
DEVICE_NAME_KEY = LS.DEVICE_NAME_KEY
DEVICE_TYPE_KEY = LS.DEVICE_TYPE_KEY
DIGITAL_DOORLOCK_ALARM_EVENT_KEY = LS.DIGITAL_DOORLOCK_ALARM_EVENT_KEY
DIGITAL_DOORLOCK_LOCK_EVENT_KEY = LS.DIGITAL_DOORLOCK_LOCK_EVENT_KEY
DOMAIN = LS.DOMAIN
GENERIC_CONTROLLER_TYPES = LS.GENERIC_CONTROLLER_TYPES
GUARD_SENSOR_TYPES = LS.GUARD_SENSOR_TYPES
HUB_ID_KEY = LS.HUB_ID_KEY
LIFESMART_SIGNAL_UPDATE_ENTITY = LS.LIFESMART_SIGNAL_UPDATE_ENTITY
LOCK_TYPES = LS.LOCK_TYPES
MANUFACTURER = LS.MANUFACTURER
MOTION_SENSOR_TYPES = LS.MOTION_SENSOR_TYPES
SUBDEVICE_INDEX_KEY = LS.SUBDEVICE_INDEX_KEY

async def async_setup_entry(hass, config_entry, async_add_entities):
    store = hass.data[DOMAIN][config_entry.entry_id]
    devices = store["devices"]; exclude_devices = store["exclude_devices"]; exclude_hubs = store["exclude_hubs"]; client = store["client"]
    out = []
    for device in devices:
        if device[DEVICE_ID_KEY] in exclude_devices or device[HUB_ID_KEY] in exclude_hubs: continue
        device_type = device[DEVICE_TYPE_KEY]
        if device_type not in (BINARY_SENSOR_TYPES + LOCK_TYPES): continue
        ha_device = LifeSmartDevice(device, client)
        for sub_key, sub_data in device[DEVICE_DATA_KEY].items():
            if device_type in GENERIC_CONTROLLER_TYPES and sub_key in ("P5", "P6", "P7"):
                out.append(LifeSmartBinarySensor(ha_device, device, sub_key, sub_data, client))
            elif device_type in LOCK_TYPES and sub_key in (DIGITAL_DOORLOCK_LOCK_EVENT_KEY, DIGITAL_DOORLOCK_ALARM_EVENT_KEY):
                out.append(LifeSmartBinarySensor(ha_device, device, sub_key, sub_data, client))
            elif device_type in BINARY_SENSOR_TYPES and sub_key in ("M", "G", "B", "AXS", "P1"):
                out.append(LifeSmartBinarySensor(ha_device, device, sub_key, sub_data, client))
    async_add_entities(out)

class LifeSmartBinarySensor(BinarySensorEntity):
    def __init__(self, device, raw, sub_key, sub_data, client) -> None:
        super().__init__()
        self._attrs: dict[str, Any] = {}
        self.sensor_device_name = raw[DEVICE_NAME_KEY]
        self.device_type = raw[DEVICE_TYPE_KEY]
        self.hub_id = raw[HUB_ID_KEY]
        self.device_id = raw[DEVICE_ID_KEY]
        self.sub_device_key = sub_key
        self.raw_device_data = raw
        self._device = device
        self._client = client
        self.device_name = sub_data.get(DEVICE_NAME_KEY) or self.sensor_device_name
        self.entity_id = generate_entity_id(self.device_type, self.hub_id, self.device_id, sub_key)
        if self.device_type in GUARD_SENSOR_TYPES:
            if sub_key == "G":
                self._device_class = BinarySensorDeviceClass.DOOR
                self._state = (sub_data.get("val", 1) == 0)
            elif sub_key == "AXS":
                self._device_class = BinarySensorDeviceClass.VIBRATION
                self._state = (sub_data.get("val", 0) != 0)
            elif sub_key == "B":
                self._device_class = None
                self._state = (sub_data.get("val", 0) != 0)
            else:
                self._device_class = None
                self._state = (sub_data.get("val", 0) != 0)
        elif self.device_type in MOTION_SENSOR_TYPES:
            self._device_class = BinarySensorDeviceClass.MOTION
            self._state = (sub_data.get("val", 0) != 0)
        elif self.device_type in LOCK_TYPES and sub_key == DIGITAL_DOORLOCK_LOCK_EVENT_KEY:
            self.device_name = "Status"
            self._device_class = BinarySensorDeviceClass.LOCK
            self._state = is_doorlock_unlocked(sub_data)
            self._attrs = build_doorlock_attribute(sub_data)
        elif self.device_type in LOCK_TYPES and sub_key == DIGITAL_DOORLOCK_ALARM_EVENT_KEY:
            self.device_name = "Alarm"
            self._device_class = BinarySensorDeviceClass.PROBLEM
            v = sub_data.get("val", 0)
            self._state = (v > 0)
            self._attrs = {"raw": v}
        elif self.device_type in GENERIC_CONTROLLER_TYPES:
            self._device_class = BinarySensorDeviceClass.LOCK
            self._state = (sub_data.get("val", 1) == 0)
            self._attrs = sub_data
        else:
            self._device_class = BinarySensorDeviceClass.SMOKE
            self._state = (sub_data.get("val", 0) != 0)

    @property
    def name(self): return self.device_name
    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.hub_id, self.device_id)},
            name=self.sensor_device_name, manufacturer=MANUFACTURER, model=self.device_type,
            sw_version=self.raw_device_data.get("ver"), via_device=(DOMAIN, self.hub_id),
        )
    @property
    def is_on(self): return self._state
    @property
    def device_class(self): return self._device_class
    @property
    def unique_id(self): return self.entity_id

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{LIFESMART_SIGNAL_UPDATE_ENTITY}_{self.entity_id}", self._update_state
            )
        )

    async def _update_state(self, data) -> None:
        if not data: return
        dev_type = data[DEVICE_TYPE_KEY]; sub_key = data[SUBDEVICE_INDEX_KEY]
        if dev_type in LOCK_TYPES and sub_key == DIGITAL_DOORLOCK_LOCK_EVENT_KEY:
            self._state = is_doorlock_unlocked(data); self._attrs = build_doorlock_attribute(data)
            self.async_write_ha_state(); return
        if dev_type in GENERIC_CONTROLLER_TYPES and sub_key in ("P5", "P6", "P7"):
            self._state = (data.get("val", 1) == 0)
        else:
            self._state = (data.get("val", 0) != 0)
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]: return getattr(self, "_attrs", {})

def extract_doorlock_unlocking_method(data):
    code = (data.get("val", 0) >> 12) & 0xF
    return {1:"Password",2:"Fingerprint",3:"NFC",4:"Mechanical key",5:"Remote unlocking",6:"One-button opening",7:"APP",8:"Bluetooth",9:"Manual unlock",15:"Error"}.get(code,"Undefined")
def is_doorlock_unlocked(data): return data.get("type", 0) % 2 == 1
def get_doorlock_unlocking_user(data): return data.get("val", 0) & 0xFFF
def build_doorlock_attribute(data): return {"unlocking_method": extract_doorlock_unlocking_method(data), "unlocking_user": get_doorlock_unlocking_user(data)}
