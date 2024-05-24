"""Support for Dirigera open/close binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

# from .const import DOMAIN as DIRIGERA_DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Dirigera open/close sensor based on a config entry."""


class DirigeraOpenCloseBinarySensor(BinarySensorEntity):
    """Binary sensor that reports if water is detected (for leak detectors)."""

    _attr_device_class = BinarySensorDeviceClass.OPENING
    _attr_translation_key = "water_detected"

    def __init__(self, device):
        """Initialize the pending alerts binary sensor."""
        super().__init__("water_detected", device)

    @property
    def is_on(self):
        """Return true if the Flo device is detecting water."""
        return self._device.water_detected
