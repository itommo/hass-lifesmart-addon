from __future__ import annotations
from typing import Any

async def async_create_client(hass, data: dict, options: dict) -> Any:
    return DummyClient()

class DummyClient:
    """Returns a hard-coded device for sanity checks."""
    async def async_get_devices(self) -> list[dict]:
        # Minimal shape: device dict with keys your platform expects
        return [{
            "devtype": "V_AIR_P",    # so climate fallback can attach
            "name": "Dummy VRV",
            "agt": "HUB123456",
            "me": "DEV001",
            "data": { "O": {"type":1}, "MODE":{"val":1}, "T":{"v":24}, "tT":{"v":22}, "F":{"val":45} },
            "ver": "debug",
            "id": "DEV001", "hub": "HUB123456"
        }]

    # Optional message subscription hooks used by the bridge (no-op here)
    def add_message_callback(self, cb): pass
    def remove_message_callback(self, cb): pass
