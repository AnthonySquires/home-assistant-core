"""The IKEA DIRIGERA integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

import dirigera

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant

# Lets only support open/close sensors for now
PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR]

_LOGGER = logging.getLogger(__name__)


@dataclass
class DirigeraData:
    """data for dirigera hub integration."""

    hub: dirigera.Hub


type DirigeraConfigEntry = ConfigEntry[DirigeraData]  # noqa: F821


async def async_setup_entry(hass: HomeAssistant, entry: DirigeraConfigEntry) -> bool:
    """Set up IKEA DIRIGERA from a config entry."""

    _LOGGER.debug("setup lets go! %s", entry.data)

    if not (hub_token := entry.data[CONF_TOKEN]):
        return False

    _LOGGER.debug("token: %s", hub_token)

    # TODOX 1. Create API instance
    # TODOX 2. Validate the API connection (and authentication)
    # TODOX 3. Store an API object for your platforms to access
    # entry.runtime_data = MyAPI(...)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DirigeraConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
