"""Support for Dirigera environment sensors."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import logging
from typing import Any

from dirigera.devices.environment_sensor import EnvironmentSensor

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_BATTERY_LEVEL, PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import DirigeraBaseEntity
from .hub import AsyncHub
from .models import DirigeraData

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class DirigeraSensorDescription:
    """Class describing Dirigera sensor entities."""

    device_class: SensorDeviceClass
    init_fn: Callable[[EnvironmentSensor], float]
    upd_fn: Callable[[dict[str, Any]], float | None]
    key: str
    suffix: str
    unit: str


SENSOR_TYPES: tuple[DirigeraSensorDescription, ...] = (
    DirigeraSensorDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        init_fn=lambda env_sensor: env_sensor.attributes.current_temperature,
        upd_fn=lambda attrs: attrs.get("currentTemperature"),
        key="temp",
        suffix="Temperature",
        unit=UnitOfTemperature.CELSIUS,
    ),
    DirigeraSensorDescription(
        device_class=SensorDeviceClass.HUMIDITY,
        init_fn=lambda env_sensor: float(env_sensor.attributes.current_r_h),
        upd_fn=lambda attrs: attrs.get("currentRH"),
        key="humi",
        suffix="Humidity",
        unit=PERCENTAGE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Dirigera environment sensor based on a config entry."""
    data: DirigeraData = entry.runtime_data
    hub = data.hub

    if not (sensors := hub.get_cached_environment_sensors()):
        return

    _LOGGER.debug("adding %d environment sensors", len(sensors))

    to_add: list[Entity] = []

    for sensor in sensors:
        if hub.update_entities(sensor.id, sensor):
            continue

        for desc in SENSOR_TYPES:
            target_id = f"{sensor.id}-{desc.key}"
            to_add.append(DirigeraEnvironmentSensor(target_id, sensor, desc, hub))

    if to_add:
        async_add_entities(to_add)


class DirigeraEnvironmentSensor(DirigeraBaseEntity, SensorEntity):
    """Sensor that reports humidity or temperature."""

    _desc: DirigeraSensorDescription
    _hub: AsyncHub

    _battery_level: int

    def __init__(
        self,
        target_id: str,
        sensor: EnvironmentSensor,
        desc: DirigeraSensorDescription,
        hub: AsyncHub,
    ) -> None:
        """Initialize the open/close sensor."""

        super().__init__(
            sensor.attributes.custom_name, target_id, sensor, sensor.attributes
        )

        self._desc = desc
        self._hub = hub

        self._attr_name = f"{sensor.attributes.custom_name} {desc.suffix}"
        self._attr_device_class = desc.device_class

        self._attr_native_unit_of_measurement = desc.unit
        self._attr_native_value = desc.init_fn(sensor)

        self._battery_level = 0

    # pylint: disable-next=hass-missing-super-call
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._hub.add_entity(self, self._update_attrs)

    @callback
    def _update_attrs(self, contents: Any) -> None:
        if attrs := contents.get("attributes"):
            if (battery_percentage := attrs.get("batteryPercentage")) is not None:
                self._battery_level = int(battery_percentage)

            if (custom_name := attrs.get("customName")) is not None:
                self._attr_name = custom_name

            if (updated_value := self._desc.upd_fn(attrs)) is not None:
                self._attr_native_value = updated_value

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
