"""The Dirigera integration models."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry

from .hub import AsyncHub


@dataclass
class DirigeraData:
    """data for dirigera hub integration."""

    hub: AsyncHub


type DirigeraConfigEntry = ConfigEntry[DirigeraData]  # noqa: F821
