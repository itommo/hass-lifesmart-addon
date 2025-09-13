from __future__ import annotations
from typing import Any

async def async_create_client(hass, data: dict, options: dict) -> Any:
    return DummyClient()

class DummyClient:
    async def async_get_devices(self) -> list[dict]:
        return [{
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
    def add_message_callback(self, cb): pass
    def remove_message_callback(self, cb): pass
