"Config flow for Mopidy."""
import logging
from typing import Optional

from mopidyapi import MopidyAPI
import voluptuous as vol
from requests.exceptions import ConnectionError as reConnectionError

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_HOST, CONF_ID, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.typing import DiscoveryInfoType
#from homeassistant.helpers.config_entry_flow

from .const import DOMAIN, DEFAULT_NAME, DEFAULT_PORT

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
        {vol.Required(CONF_NAME): str, vol.Required(CONF_HOST): str,vol.Required(CONF_PORT, default=DEFAULT_PORT): int}
)

async def validate_input(hass, host, port):
    """Validate user input"""
    try:
        client = MopidyAPI(
            host=host, port=port, use_websocket=False
        )
        return client.rpc_call("core.get_version")
    except reConnectionError as error:
        raise CannotConnect from error

class MopidyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for Mopidy Servers."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize flow"""
        self._host: Optional[str] = None
        self._port: Optional[int] = None
        self._name: Optional[str] = None
        self._uuid: Optional[str] = None

    @callback
    def _async_get_entry(self):
        return self.async_create_entry(
            title=self._name,
            data={
                CONF_NAME: self._name,
                CONF_HOST: self._host,
                CONF_PORT: self._port
            },
        )

    async def _set_uid_and_abort(self):
        await self.async_set_unique_id(self._uuid)
        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: self._host,
                CONF_PORT: self._port,
                CONF_NAME: self._name
            }
        )

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            info = None
            self._host = user_input[CONF_HOST]
            self._port = user_input[CONF_PORT]
            try:
                info = await validate_input(self.hass, self._host, self._port)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if info is not None:
                self._name = user_input[CONF_NAME]

                return self._async_get_entry()

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_zeroconf(self, discovery_info: DiscoveryInfoType):
        """Handle zeroconf discovery."""
        self._host = discovery_info["host"]
        self._port = int(discovery_info["port"])
        self._name = discovery_info["properties"]["volumioName"]
        self._uuid = discovery_info["properties"]["UUID"]

        await self._set_uid_and_abort()

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(self, user_input=None):
        """Handle user-confirmation of discovered node."""
        if user_input is not None:
            try:
                await validate_input(self.hass, self._host, self._port)
                return self._async_get_entry()
            except CannotConnect:
                return self.async_abort(reason="cannot_connect")

        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders={"name": self._name}
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
