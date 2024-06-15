"""Dirigera hub async wrapper."""

from collections.abc import Callable
from dataclasses import dataclass
import json
import logging
import threading
import time
from typing import Any

import dirigera
from dirigera.devices.environment_sensor import (
    EnvironmentSensor,
    dict_to_environment_sensor,
)
from dirigera.devices.open_close_sensor import (
    OpenCloseSensor,
    dict_to_open_close_sensor,
)
import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .base import DirigeraBaseEntity
from .const import PLATFORMS

_LOGGER = logging.getLogger(__name__)


def fixup_env_sensor(raw: dict[str, Any]) -> dict[str, Any]:
    """Process a raw environment sensor to produce a compatible dict for the dirigera library to consume."""

    if not (attributes := raw.get("attributes")):
        attributes = {}
        raw.update(
            {
                "attributes": attributes,
            }
        )

    if "currentTemperature" not in attributes:
        attributes["currentTemperature"] = None

    if "currentRH" not in attributes:
        attributes["currentRH"] = None

    if "currentPM25" not in attributes:
        attributes["currentPM25"] = None

    if "maxMeasuredPM25" not in attributes:
        attributes["maxMeasuredPM25"] = None

    if "minMeasuredPM25" not in attributes:
        attributes["minMeasuredPM25"] = None

    if "vocIndex" not in attributes:
        attributes["vocIndex"] = None

    return raw


class Backoff:
    """Holds exponential backoff state for retries."""

    _STEPS = [1, 1, 2, 3, 5, 8, 13, 20]
    _idx: int

    def __init__(self) -> None:
        """Set up backoff to start at 1 second."""

        self._idx = 0

    def reset(self):
        """Reset the counter backoff to the initial state."""

        self._idx = 0

    def get(self) -> int:
        """Retrieve the current value and advance the index to the next."""

        val = self._STEPS[self._idx]
        if self._idx <= len(self._STEPS):
            self._idx += 1

        return val


@dataclass
class CachedDevices:
    """A cache of the most recent full device fetch from the hub."""

    locations: dict[str, str]
    environment_sensors: list[EnvironmentSensor]
    open_close_sensors: list[OpenCloseSensor]


class AsyncHub:
    """an async wrapper for the dirigera hub API."""

    _config_entry: ConfigEntry
    _hub_host: str
    _hub_token: str

    _backoff: Backoff
    _cache: CachedDevices
    _entities: dict[str, DirigeraBaseEntity]
    _hass: HomeAssistant
    _hub: dirigera.Hub
    _running: bool
    _subscribers: dict[str, list[Callable[[Any], None]]]
    _ws_thrd: threading.Thread | None

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        host: str,
        token: str,
    ) -> None:
        """Initialize the hub."""

        self._config_entry = config_entry
        self._hub_host = host
        self._hub_token = token

        self._backoff = Backoff()
        self._entities = {}
        self._event_listener = None
        self._hass = hass
        self._hub = None
        self._running = False
        self._subscribers = {}
        self._ws_thrd = None

    async def start_event_listener(self) -> None:
        """Start listening for events on any device."""

        self._running = True

        self._ws_thrd = threading.Thread(target=self._run_events)
        self._ws_thrd.start()

    async def stop_event_listener(self) -> None:
        """Stop the inprogress events websocket."""

        self._running = False

        await self._hass.async_add_executor_job(self._hub.stop_event_listener)
        if self._ws_thrd:
            await self._hass.async_add_executor_job(self._ws_thrd.join, 15)

    def get_cached_location(self, device_id: str) -> str | None:
        """Retrieve the last known location for device_id."""

        if not self._cache:
            return None

        return self._cache.locations.get(device_id)

    def get_cached_environment_sensors(self) -> list[EnvironmentSensor] | None:
        """Retrieve the list of environments sensors."""

        if not self._cache:
            return None

        return self._cache.environment_sensors

    def get_cached_open_close_sensors(self) -> list[OpenCloseSensor] | None:
        """Retrieve the list of open/close sensors."""

        if not self._cache:
            return None

        return self._cache.open_close_sensors

    def add_entity(
        self,
        ent: DirigeraBaseEntity,
        event_callback: Callable[[Any], None],
    ) -> None:
        """Add a subscriber to receive events."""

        self._entities[ent.id] = ent

        if subscriptions := self._subscribers.get(ent.device_id):
            subscriptions.append(event_callback)
        else:
            self._subscribers[ent.device_id] = [event_callback]

    def update_entities(self, id: str, contents: Any) -> bool:
        """Update an entity if it exists and is registered. Otherwise return false."""

        if subscriptions := self._subscribers.get(id):
            for sub in subscriptions:
                self._hass.add_job(sub, contents)
            return True

        return False

    def _on_close(self, ws, a, b) -> None:
        _LOGGER.debug("Dirigera connection closed")

    def _on_error(self, ws, message: str) -> None:
        _LOGGER.debug("Dirigera connection error: %s", message)

    def _on_message(self, ws, message: str) -> None:
        if not (message_dict := json.loads(message)):
            return

        if not (data := message_dict.get("data")):
            return

        if not (target_id := data.get("id")):
            return

        if subscriptions := self._subscribers.get(target_id):
            for sub in subscriptions:
                self._hass.add_job(sub, data)

    def _on_open(self, ws) -> None:
        self._backoff.reset()

    def _run_events(self):
        while self._running:
            if not self._hub:
                self._setup_hub()
            if not self._running:
                break
            self._hub.create_event_listener(
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open,
            )

    def _set_availability(self, available: bool):
        _LOGGER.debug("Dirigera hub %s", "available" if available else "unavailable")
        for ent in self._entities.values():
            self._hass.add_job(ent.set_available, available)

    def _setup_hub(self) -> None:
        _LOGGER.debug("Dirigera hub setup")

        self._set_availability(False)

        while not self._hub:
            _LOGGER.debug("Dirigera init hub")
            self._hub = dirigera.Hub(self._hub_token, self._hub_host)
            _LOGGER.debug("Dirigera hub fetch")
            try:
                res = self._hub.get("/devices")
            except requests.HTTPError as e:
                _LOGGER.warning(
                    "Dirigera failed to fetch devices. Will attempt retry: %s", e
                )
                self._hub = None
                time.sleep(self._backoff.get())

        for d in res:
            if d.get("deviceType") == "environmentSensor":
                logging.debug("debug %s", d)

        self._cache = CachedDevices(
            locations={},
            environment_sensors=[
                dict_to_environment_sensor(fixup_env_sensor(d), self._hub)
                for d in res
                if d.get("deviceType") == "environmentSensor"
            ],
            open_close_sensors=[
                dict_to_open_close_sensor(d, self._hub)
                for d in res
                if d.get("deviceType") == "openCloseSensor"
            ],
        )

        for d in res:
            if device_id := d.get("id"):
                if location := d.get("customIcon"):
                    self._cache.locations[device_id] = location

        self._set_availability(True)
        self._hass.add_job(
            self._hass.config_entries.async_forward_entry_setups,
            self._config_entry,
            PLATFORMS,
        )
