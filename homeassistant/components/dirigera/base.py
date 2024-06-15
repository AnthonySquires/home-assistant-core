"""A basic wrapper for common dirigera functions."""

from abc import ABC
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from dirigera.devices.device import Attributes, Device

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

ATTR_LAST_SEEN = "time_last_seen"


class DirigeraBaseEntity(ABC, Entity):
    """Base entity."""

    _device_id: str
    _last_seen: datetime
    _uid: str

    def __init__(
        self, device_name: str, uid: str, device: Device, base_attributes: Attributes
    ) -> None:
        """Initialize a base entity from base dirigera types."""

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            manufacturer=base_attributes.manufacturer,
            hw_version=base_attributes.hardware_version,
            model=base_attributes.model,
            name=device_name,
            serial_number=base_attributes.serial_number,
            suggested_area=device.room.name,
            sw_version=base_attributes.firmware_version,
        )

        self._attr_available = device.is_reachable
        self._attr_id = uid
        self._attr_unique_id = uid
        self._device_id = device.id
        self._last_seen = device.last_seen
        self._uid = uid

    @property
    def device_id(self) -> str:
        """Return the base device ID of the entity."""

        return self._device_id

    @property
    def id(self) -> str:
        """Return the unique ID of the entity which may include it's subtype."""
        return self._uid

    @callback
    async def set_available(self, available: bool) -> None:
        """Set the evailability state of the sensor."""

        self._attr_available = available
        self.async_write_ha_state()

    @callback
    def _update_attrs(self, contents: Any) -> None:
        """Update attributes from either an update dict or a mapped object."""

        if (reachable := contents.get("isReachable")) is not None:
            self._attr_available = reachable

        if last_seen_str := contents.get("lastSeen"):
            self._last_seen = datetime.fromisoformat(last_seen_str)

        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return the last seen time."""
        super_attrs = super().extra_state_attributes
        attrs: dict[str, Any] = dict(super_attrs) if super_attrs else {}

        if self._last_seen:
            attrs[ATTR_LAST_SEEN] = str(self._last_seen)

        return attrs
