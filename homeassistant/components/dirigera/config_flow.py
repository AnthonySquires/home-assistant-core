"""Config flow for IKEA DIRIGERA."""

import logging
import string
from typing import Any

from dirigera.hub.auth import get_token, random_code, send_challenge

from homeassistant.components import zeroconf
from homeassistant.config_entries import SOURCE_ZEROCONF, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_TOKEN, CONF_UUID
from homeassistant.core import callback

# from homeassistant.helpers import config_entry_flow
from .const import DOMAIN, MDNS_ATTR_HOSTNAME, MDNS_ATTR_IPV4, MDNS_ATTR_UUID

_LOGGER = logging.getLogger(__name__)

ALPHABET = f"_-~.{string.ascii_letters}{string.digits}"
CODE_LENGTH = 128


class DirigeraConfigFlow(ConfigFlow, domain=DOMAIN):
    """Dirigera config flow."""

    data: dict[str, Any]
    pair_code_verifier: str | None
    pair_code: str | None

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}
        self.pair_code_verifier = None
        self.pair_code = None

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        await self.async_set_unique_id(discovery_info.properties[MDNS_ATTR_UUID])
        self._abort_if_unique_id_configured({CONF_HOST: discovery_info.host})

        # session = async_get_clientsession(self.hass)
        # air_gradient = AirGradientClient(host, session=session)
        # await air_gradient.get_current_measures()

        self.data[CONF_HOST] = discovery_info.properties[MDNS_ATTR_IPV4]
        self.data[CONF_MODEL] = discovery_info.properties[MDNS_ATTR_HOSTNAME][-6:]
        self.data[CONF_UUID] = discovery_info.properties[MDNS_ATTR_UUID]

        self.context.update(
            {
                "host": discovery_info.host,
                "title_placeholders": {"model": self.data[CONF_MODEL]},
            }
        )
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        if user_input is not None:
            _LOGGER.debug("yo %s", user_input)

            return await self.async_step_pair_action()

            #

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "model": self.data[CONF_MODEL],
                "uuid": self.data[CONF_UUID],
            },
        )

    async def async_step_pair_action(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle step where user has to press the action button on the device."""

        if not (host := self.data[CONF_HOST]):
            return self.async_abort(reason="no_host_set")

        self.pair_code_verifier = random_code(ALPHABET, CODE_LENGTH)
        self.pair_code = await self.hass.async_add_executor_job(
            send_challenge, host, self.pair_code_verifier
        )

        _LOGGER.debug("code: %s", self.pair_code)

        self._set_confirm_only()
        return self.async_show_form(
            step_id="user",
            description_placeholders={
                "model": self.data[CONF_MODEL],
            },
        )

    @callback
    def _get_discovered_entries(self) -> dict[str, str]:
        """Get discovered entries."""
        entries: dict[str, str] = {}

        _LOGGER.debug("yo1")

        for flow in self._async_in_progress(include_uninitialized=True):
            _LOGGER.debug("yo1b %s", flow)
            if flow["context"]["source"] == SOURCE_ZEROCONF:
                info = flow["context"]["title_placeholders"]
                entries[flow["context"]["host"]] = (
                    f"{info['model']} ({info['device_id']})"
                )

        _LOGGER.debug("yo2")
        return entries

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        if user_input is not None:
            if not (host := self.data[CONF_HOST]):
                return self.async_abort(reason="no_host_set")

            token = await self.hass.async_add_executor_job(
                get_token, host, self.pair_code, self.pair_code_verifier
            )

            _LOGGER.debug("token: %s", token)

            return self.async_create_entry(
                title=self.data[CONF_MODEL],
                data={
                    CONF_HOST: self.data[CONF_HOST],
                    CONF_MODEL: self.data[CONF_MODEL],
                    CONF_TOKEN: token,
                    CONF_UUID: self.data[CONF_UUID],
                },
            )

        return self.async_show_menu(step_id="user", menu_options=["local", "cloud"])
