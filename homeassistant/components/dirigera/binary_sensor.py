"""Support for Dirigera open/close binary sensors."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from dirigera.devices.open_close_sensor import OpenCloseSensor

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_BATTERY_LEVEL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import DirigeraBaseEntity
from .helpers import split_name_location
from .hub import AsyncHub
from .models import DirigeraData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Dirigera open/close sensor based on a config entry."""

    data: DirigeraData = entry.runtime_data
    hub = data.hub

    if not (sensors := hub.get_cached_open_close_sensors()):
        return

    _LOGGER.debug("adding %d open/close sensors", len(sensors))

    to_add: list[Entity] = [
        DirigeraOpenCloseBinarySensor(sensor, hub.get_cached_location(sensor.id), hub)
        for sensor in sensors
        if not hub.update_entities(sensor.id, sensor)
    ]

    if to_add:
        async_add_entities(to_add)


def placement_to_class(
    location: str | None, custom_location: str | None
) -> BinarySensorDeviceClass:
    """Convert an OpenCloseSensor location to a device class."""

    if location == "placement_door":
        return BinarySensorDeviceClass.DOOR
    if location == "placement_window":
        return BinarySensorDeviceClass.WINDOW
    if location == "placement_other":
        if not custom_location:
            return BinarySensorDeviceClass.OPENING

        for device in BinarySensorDeviceClass:
            if device.value == custom_location.lower():
                return device

    if location in {"placement_cabinet", "placement_wardrobe"}:
        return BinarySensorDeviceClass.OPENING

    _LOGGER.debug("unknown location: %s (%s)", location, custom_location)
    return BinarySensorDeviceClass.OPENING


class DirigeraOpenCloseBinarySensor(DirigeraBaseEntity, BinarySensorEntity):
    """Binary sensor that reports if some object is open or closed."""

    _hub: AsyncHub

    _battery_level: int
    _custom_location: str | None
    _location: str | None

    def __init__(
        self, sensor: OpenCloseSensor, location: str | None, hub: AsyncHub
    ) -> None:
        """Initialize the open/close sensor."""

        real_name, custom_location = split_name_location(sensor.attributes.custom_name)

        super().__init__(real_name, sensor.id, sensor, sensor.attributes)

        self._hub = hub

        self._battery_level = sensor.attributes.battery_percentage
        self._custom_location = custom_location
        self._location = location

        self._attr_name = real_name
        self._attr_device_class = placement_to_class(location, custom_location)
        self._attr_is_on = sensor.attributes.is_open

    # pylint: disable-next=hass-missing-super-call
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._hub.add_entity(self, self._update_attrs)

    @callback
    def _update_attrs(self, contents: Any) -> None:
        if custom_icon := contents.get("customIcon"):
            self._location = custom_icon
            self._attr_device_class = placement_to_class(
                self._location, self._custom_location
            )

        if attrs := contents.get("attributes"):
            if (battery_percentage := attrs.get("batteryPercentage")) is not None:
                self._battery_level = int(battery_percentage)

            if (custom_name := attrs.get("customName")) is not None:
                real_name, custom_location = split_name_location(custom_name)
                self._attr_device_class = placement_to_class(
                    self._location, self._custom_location
                )
                self._attr_name = real_name
                self._custom_location = custom_location

            if (is_open := attrs.get("isOpen")) is not None:
                self._attr_is_on = is_open

        # super called last because it triggers the attr update
        super()._update_attrs(contents)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return the extra battery info I guess."""
        super_attrs = super().extra_state_attributes
        attrs: dict[str, Any] = dict(super_attrs) if super_attrs else {}

        if self._battery_level:
            attrs[ATTR_BATTERY_LEVEL] = self._battery_level
        return attrs
