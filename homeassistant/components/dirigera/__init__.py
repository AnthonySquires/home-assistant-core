"""The IKEA DIRIGERA integration."""

from __future__ import annotations

import logging

from homeassistant.const import CONF_HOST, CONF_TOKEN, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant

from .const import PLATFORMS
from .hub import AsyncHub
from .models import DirigeraConfigEntry, DirigeraData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: DirigeraConfigEntry) -> bool:
    """Set up IKEA DIRIGERA from a config entry."""

    _LOGGER.debug("setup lets go! %s", entry.data)

    if not (hub_host := entry.data[CONF_HOST]):
        return False

    if not (hub_token := entry.data[CONF_TOKEN]):
        return False

    async_hub = AsyncHub(hass, entry, hub_host, hub_token)

    async def on_hass_stop(event: Event) -> None:
        """Close connection when hass stops."""
        await async_hub.stop_event_listener()

    # Setup listeners
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)
    )

    entry.runtime_data = DirigeraData(
        hub=async_hub,
    )

    await async_hub.start_event_listener()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DirigeraConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
