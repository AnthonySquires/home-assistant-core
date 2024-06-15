"""Constants for the IKEA DIRIGERA integration."""

from homeassistant.const import Platform

DOMAIN = "dirigera"

MDNS_ATTR_HOSTNAME = "hostname"
MDNS_ATTR_IPV4 = "ipv4address"
MDNS_ATTR_UUID = "uuid"

# Lets only support open/close sensors for now
PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]
