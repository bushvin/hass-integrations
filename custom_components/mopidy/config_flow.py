"""Config flow for Mopidy."""
import logging
import re
import socket
from typing import Optional

from mopidyapi import MopidyAPI
from requests.exceptions import ConnectionError as reConnectionError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_ID, CONF_NAME, CONF_PORT, CONF_TYPE
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import DEFAULT_PORT, DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


def _validate_input(host, port):
    """Validate the user input."""
    client = MopidyAPI(
        host=host,
        port=port,
        use_websocket=False,
        logger=logging.getLogger(__name__ + ".client"),
    )
    client.rpc_call("core.get_version")
    return True


class MopidyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for Mopidy Servers."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize flow."""
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
                CONF_PORT: self._port,
                CONF_ID: self._uuid,
            },
        )

    async def _set_uid_and_abort(self):
        await self.async_set_unique_id(self._uuid)
        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: self._host,
                CONF_PORT: self._port,
                CONF_NAME: self._name,
            }
        )

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._port = user_input[CONF_PORT]
            self._name = user_input[CONF_NAME]
            self._uuid = re.sub(r"[._-]+", "_", self._host) + "_" + str(self._port)

            try:
                await self.hass.async_add_executor_job(
                    _validate_input, self._host, self._port
                )
            except reConnectionError:
                _LOGGER.error("Can't connect to %s:%d", self._host, self._port)
                errors["base"] = "cannot_connect"
            except:  # noqa: E722 # pylint: disable=bare-except
                _LOGGER.exception(
                    "Unexpected exception connecting to %s:%d", self._host, self._port
                )
                errors["base"] = "unknown"

            if not errors:
                await self._set_uid_and_abort()
                return self._async_get_entry()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): cv.string,
                    vol.Required(CONF_HOST): cv.string,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.positive_int,
                }
            ),
            errors=errors,
        )

    async def async_step_zeroconf(self, discovery_info: DiscoveryInfoType):
        """Handle zeroconf discovery."""
        # Get mDNS address.
        mdns_address = discovery_info.hostname[:-1]

        # Try to resolve mDNS address (no Docker HASS scenario)
        try:
            socket.gethostbyname(mdns_address)
            # If success, use the mDNS address as host.
            host = mdns_address

        # Otherwise:
        except socket.gaierror:

            # Try to reverse solve the IP to a DNS name (Docker HASS with reachable local DNS scenario)
            try:
                ip_address = discovery_info.host
                host = socket.gethostbyaddr(ip_address)[0]

            # Fallback on IP in last resort (Docker HASS without local DNS scenario)
            except socket.gaierror:
                host = ip_address

        # Set host.
        self._host = host
        # Set port.
        self._port = int(discovery_info.port)
        # Set name.
        self._name = (
            getattr(discovery_info, CONF_NAME)[: (len(getattr(discovery_info, CONF_TYPE)) +1) * -1]
            + "@"
            + str(self._port)
        )
        # Set UUID.
        node_name = mdns_address.rsplit(".")[0]
        self._uuid = node_name + "_" + str(self._port)

        await self._set_uid_and_abort()

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(self, user_input=None):
        """Handle user-confirmation of discovered node."""
        if user_input is not None:
            try:
                await self.hass.async_add_executor_job(
                    _validate_input, self._host, self._port
                )

                return self._async_get_entry()
            except reConnectionError:
                return self.async_abort(reason="cannot_connect")

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "name": self._name,
                "host": self._host,
                "port": self._port,
            },
        )
