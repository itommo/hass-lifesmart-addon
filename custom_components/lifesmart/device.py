from __future__ import annotations
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

def _slug(s: Any) -> str:
    return str(s).lower().replace(":", "_").replace("@", "_")

def generate_entity_id(device_type: Any, hub_id: Any, device_id: Any, sub_key: Any) -> str:
    return f"{_slug(device_type)}_{_slug(hub_id)}_{_slug(device_id)}_{_slug(sub_key)}"

class LifeSmartDevice:
    """Lightweight base so platform files can import safely."""
    def __init__(self, raw_device: dict, client: Any, *_, **__) -> None:
        self._raw = raw_device
        self._client = client
        self._attributes: dict[str, Any] = {}

    async def async_lifesmart_epset(self, code: str, value: Any, key: str) -> int:
        """Best-effort setter; won’t crash if client methods are absent."""
        if not self._client:
            _LOGGER.debug("LifeSmartDevice: no client; epset(%s,%s,%s) ignored", code, value, key)
            return 0
        for name in ("async_epset", "async_set", "epset", "set", "async_send", "send"):
            if hasattr(self._client, name):
                try:
                    fn = getattr(self._client, name)
                    res = fn(code, value, key)
                    if hasattr(res, "__await__"):
                        res = await res
                    return 0 if res is None else int(res) if isinstance(res, int) else 0
                except Exception as exc:
                    _LOGGER.debug("LifeSmartDevice: %s failed: %s", name, exc)
                    break
        return 0
