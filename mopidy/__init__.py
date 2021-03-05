"""The mopidy component."""
from mopidyapi import MopidyAPI
import logging
from requests.exceptions import ConnectionError as reConnectionError
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.const import CONF_HOST, CONF_ID, CONF_NAME, CONF_PORT

from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the mopidy component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the mopidy from a config entry."""

    try:
        client = MopidyAPI(
            host=entry.data[CONF_HOST], port=entry.data[CONF_PORT], use_websocket=False
        )
        i = client.rpc_call("core.get_version")

    except reConnectionError as error:
        raise ConfigEntryNotReady from error

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {"mopidy_client": client}

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, MEDIA_PLAYER_DOMAIN)
    )

    return True
