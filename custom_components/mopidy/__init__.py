"""The mopidy component."""
import logging

from mopidyapi import MopidyAPI
from requests.exceptions import ConnectionError as reConnectionError

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the mopidy component."""
    return True


def _test_connection(host, port):
    client = MopidyAPI(
        host=host,
        port=port,
        use_websocket=False,
        logger=logging.getLogger(__name__ + ".client"),
    )
    client.rpc_call("core.get_version")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the mopidy from a config entry."""
    try:
        await hass.async_add_executor_job(
            _test_connection, entry.data[CONF_HOST], entry.data[CONF_PORT]
        )

    except reConnectionError as error:
        raise ConfigEntryNotReady from error

    hass.data.setdefault(DOMAIN, {})

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, MEDIA_PLAYER_DOMAIN)
    )

    return True
