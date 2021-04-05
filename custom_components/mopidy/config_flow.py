"""Config flow for Mopidy."""
import logging
import re
from typing import Optional

from mopidyapi import MopidyAPI
from requests.exceptions import ConnectionError as reConnectionError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_ID, CONF_NAME, CONF_PORT
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import DEFAULT_PORT, DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


def _validate_input(host, port):
    """Validate the user input."""
    client = MopidyAPI(host=host, port=port, use_websocket=False)
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
            except:  # pylint: disable=bare-except
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
        try:
            await self.hass.async_add_executor_job(
                _validate_input, discovery_info["hostname"], discovery_info["port"]
            )
        except reConnectionError:
            _LOGGER.warning(
                "%s@%d is not a mopidy server",
                discovery_info["hostname"],
                discovery_info["port"],
            )
            return self.async_abort(reason="not_mopidy")
        except:  # pylint: disable=bare-except
            _LOGGER.error(
                "An error ocurred connecting to %s:%s",
                discovery_info["hostname"],
                discovery_info["port"],
            )
            return self.async_abort(reason="not_mopidy")

        _LOGGER.info(
            "Discovered a Mopidy Server @ %s (%s) on port %d",
            discovery_info["hostname"],
            discovery_info["host"],
            discovery_info["port"],
        )

        self._host = discovery_info["hostname"]
        self._port = int(discovery_info["port"])
        self._name = discovery_info["properties"].get("name", self._host)
        self._uuid = re.sub(r"[._-]+", "_", self._host) + "_" + str(self._port)

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
