"""Support to interact with a MopidyMusic Server."""
import logging
from mopidyapi import MopidyAPI
from requests.exceptions import ConnectionError as reConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerEntity,
    PLATFORM_SCHEMA,
)
from homeassistant.components.media_player.errors import BrowseError
import homeassistant.util.dt as dt_util
import homeassistant.helpers.config_validation as cv
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_ALBUM,
    MEDIA_CLASS_ARTIST,
    MEDIA_CLASS_COMPOSER,
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_GENRE,
    MEDIA_CLASS_MUSIC,
    MEDIA_CLASS_PLAYLIST,
    MEDIA_CLASS_PODCAST,
    MEDIA_CLASS_TRACK,
    MEDIA_CLASS_URL,
    MEDIA_TYPE_ALBUM,
    MEDIA_TYPE_ARTIST,
    MEDIA_TYPE_EPISODE,
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_PLAYLIST,
    MEDIA_TYPE_TRACK,
    REPEAT_MODE_ALL,
    REPEAT_MODE_OFF,
    REPEAT_MODE_ONE,
    SUPPORT_BROWSE_MEDIA,
    SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_REPEAT_SET,
    SUPPORT_SEEK,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_NAME,
    STATE_IDLE,
    STATE_UNAVAILABLE,
    STATE_PLAYING,
    STATE_PAUSED,
    STATE_UNKNOWN,
)

from .const import (
    DOMAIN,
    ICON,
)

SUPPORT_MOPIDY = (
    SUPPORT_BROWSE_MEDIA
    | SUPPORT_CLEAR_PLAYLIST
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PAUSE
    | SUPPORT_PLAY
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_REPEAT_SET
    | SUPPORT_SEEK
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_STEP
)

MEDIA_TYPE_SHOW = "show"

PLAYABLE_MEDIA_TYPES = [
    MEDIA_TYPE_PLAYLIST,
    MEDIA_TYPE_ALBUM,
    MEDIA_TYPE_ARTIST,
    MEDIA_TYPE_EPISODE,
    MEDIA_TYPE_SHOW,
    MEDIA_TYPE_TRACK,
]

_LOGGER = logging.getLogger(__name__)
DEFAULT_NAME = "Mopidy"
DEFAULT_PORT = 6680

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


class MissingMediaInformation(BrowseError):
    """Missing media required information."""


async def async_setup_platform(
    hass: HomeAssistant, config: ConfigEntry, async_add_entities, discover_info=None
):
    """Set up the Mopidy platform."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    name = config.get(CONF_NAME)

    entity = MopidyMediaPlayerEntity(host, port, name)
    async_add_entities([entity], True)


class MopidyMediaPlayerEntity(MediaPlayerEntity):
    """Representation of the Mopidy server."""

    def __init__(self, hostname, port, name):
        """Initialize the Mopidy device."""
        _LOGGER.debug("Initializing MopidyMediaPlayerEntity for %s" % name)
        self.hostname = hostname
        self.port = port
        self.device_name = name

        self.server_version = None
        self.player_currenttrack = None

        self._media_position = None
        self._media_position_updated_at = None
        self._state = STATE_UNKNOWN
        self._volume = None
        self._muted = None
        self._media_image_url = None
        self._shuffled = None
        self._repeat_mode = None

        self.client = None
        self._available = None

    def _fetch_status(self):
        """Fetch status from Mopidy."""
        _LOGGER.debug("Fetching Mopidy Server status for %s" % self.device_name)
        self.player_currenttrack = self.client.playback.get_current_track()

        media_position = int(self.client.playback.get_time_position() / 1000)
        if media_position != self._media_position:
            self._media_position = media_position
            self._media_position_updated_at = dt_util.utcnow()

        state = self.client.playback.get_state()
        if state is None:
            self._state = STATE_UNAVAILABLE
        elif state == "playing":
            self._state = STATE_PLAYING
        elif state == "paused":
            self._state = STATE_PAUSED
        elif state == "stopped":
            self._state = STATE_IDLE
        else:
            self._state = STATE_UNKNOWN

        self._volume = float(self.client.mixer.get_volume() / 100)
        self._muted = self.client.mixer.get_mute()

        if hasattr(self.player_currenttrack, "uri"):
            res = self.client.library.get_images([self.player_currenttrack.uri])
            if (
                self.player_currenttrack.uri in res
                and len(res[self.player_currenttrack.uri]) > 0
                and hasattr(res[self.player_currenttrack.uri][0], "uri")
            ):
                self._media_image_url = res[self.player_currenttrack.uri][0].uri
        else:
            self._media_image_url = None

        self._shuffled = self.client.tracklist.get_random()

        repeat = self.client.tracklist.get_repeat()
        single = self.client.tracklist.get_single()
        if repeat and single:
            self._repeat_mode = REPEAT_MODE_ONE
        elif repeat:
            self._repeat_mode = REPEAT_MODE_ALL
        else:
            self._repeat_mode = REPEAT_MODE_OFF

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self.device_name

    @property
    def icon(self) -> str:
        """Return the icon."""
        return ICON

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def state(self):
        """Return the media state."""
        return self._state

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def media_content_id(self):
        """Return the content ID of current playing media."""
        if hasattr(self.player_currenttrack, "uri"):
            return self.player_currenttrack.uri
        return None

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        if hasattr(self.player_currenttrack, "length"):
            return int(self.player_currenttrack.length / 1000)
        return None

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        return self._media_position

    @property
    def media_position_updated_at(self):
        """Last valid time of media position."""
        return self._media_position_updated_at

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        return self._media_image_url

    @property
    def media_image_remotely_accessible(self):
        """If the image url is remotely accessible."""
        return False

    @property
    def media_title(self):
        """Return the title of current playing media."""
        if hasattr(self.player_currenttrack, "name"):
            return self.player_currenttrack.name
        return None

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        if hasattr(self.player_currenttrack, "artists"):
            return ", ".join([a.name for a in self.player_currenttrack.artists])
        return None

    @property
    def media_album_name(self):
        """Album name of current playing media, music track only."""
        if hasattr(self.player_currenttrack, "album") and hasattr(
            self.player_currenttrack.album, "name"
        ):
            return self.player_currenttrack.album.name
        return None

    @property
    def media_album_artist(self):
        """Album artist of current playing media, music track only."""
        if hasattr(self.player_currenttrack, "artists"):
            return ", ".join([a.name for a in self.player_currenttrack.artists])
        return None

    @property
    def media_track(self):
        """Track number of current playing media, music track only."""
        if hasattr(self.player_currenttrack, "track_no"):
            return self.player_currenttrack.track_no
        return None

    @property
    def media_playlist(self):
        """Title of Playlist currently playing."""
        if hasattr(self.player_currenttrack, "album") and hasattr(
            self.player_currenttrack.album, "name"
        ):
            return self.player_currenttrack.album.name

        # Check what to do when it's a playlist...
        return None

    @property
    def shuffle(self):
        """Boolean if shuffle is enabled."""
        return self._shuffled

    @property
    def repeat(self):
        """Return current repeat mode."""
        return self._repeat_mode

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        # if not self._available:
        #    return 0

        return SUPPORT_MOPIDY

    def mute_volume(self, mute):
        """Mute the volume."""
        self.client.mixer.set_mute(mute)

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self.client.mixer.set_volume(int(volume * 100))

    def media_play(self):
        """Send play command."""
        self.client.playback.play()

    def media_pause(self):
        """Send pause command."""
        self.client.playback.pause()

    def media_stop(self):
        """Send stop command."""
        self.client.playback.stop()

    def media_previous_track(self):
        """Send previous track command."""
        self.client.playback.previous()

    def media_next_track(self):
        """Send next track command."""
        self.client.playback.next()

    def media_seek(self, position):
        """Send seek command."""
        self.client.playback.seek(int(position * 1000))

    def play_media(self, media_type, media_id, **kwargs):
        """Play a piece of media."""
        _LOGGER.debug("media_type: %s" % media_type)
        _LOGGER.debug("media_id: %s" % media_id)
        _LOGGER.debug("kwargs: %s" % kwargs)
        if media_id is not None:
            self.client.tracklist.clear()
            self.client.tracklist.add(uris=[media_id])

        self.client.playback.play()

    def clear_playlist(self):
        """Clear players playlist."""
        self.client.tracklist.clear()

    def set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        self.client.tracklist.set_random(shuffle)

    def set_repeat(self, repeat):
        """Set repeat mode."""
        if repeat == REPEAT_MODE_ALL:
            self.client.tracklist.set_repeat(True)
            self.client.tracklist.set_single(False)
        elif repeat == REPEAT_MODE_ONE:
            self.client.tracklist.set_repeat(True)
            self.client.tracklist.set_single(True)
        else:
            self.client.tracklist.set_repeat(False)
            self.client.tracklist.set_single(False)

    def volume_up(self):
        """Turn volume up for media player."""
        new_volume = self.client.mixer.get_volume() + 5
        if new_volume > 100:
            new_volume = 100

        self.client.mixer.set_volume(new_volume)

    def volume_down(self):
        """Turn volume down for media player."""
        new_volume = self.client.mixer.get_volume() - 5
        if new_volume < 0:
            new_volume = 0

        self.client.mixer.set_volume(new_volume)

    @property
    def device_class(self):
        """Return the device class"""
        return "speaker"

    @property
    def device_info(self):
        """Return device information about this entity."""
        return {
            "indentifiers": {(DOMAIN, self.device_name)},
            "manufacturer": "Mopidy",
            "model": "Mopidy server %s" % self.server_version,
            "name": self.device_name,
            "sw_version": self.server_version,
        }

    def _connect(self):
        try:
            self.client = MopidyAPI(
                host=self.hostname, port=self.port, use_websocket=False
            )
            self.server_version = self.client.rpc_call("core.get_version")
            _LOGGER.info(
                "Connection to Mopidy server %s (%s:%s) established"
                % (self.device_name, self.hostname, self.port)
            )
            # self.client = MopidyAPI(host=self.hostname, port=self.port)
        except reConnectionError as error:
            _LOGGER.error(
                "Cannot connect to %s @ %s:%s"
                % (self.device_name, self.hostname, self.port)
            )
            _LOGGER.error(error)
            self._available = False
            return
        self._available = True

    def update(self):
        """Get the latest data and update the state."""
        if self._available is None:
            self._connect()

        if self._available:
            self._fetch_status()

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        """Implement the websocket media browsing helper."""

        return await self.hass.async_add_executor_job(
            self._media_library_payload, media_content_type, media_content_id
        )

    def _media_item_payload(self, item):
        """Create response payload for a single media item."""
        if not hasattr(item, "type") or not hasattr(item, "uri"):
            _LOGGER.error("Missing type or uri for media item: %s", item)
            raise MissingMediaInformation
        _LOGGER.debug("%s:%s" % (item.uri, item.type))

        expandable = item.type not in [MEDIA_TYPE_TRACK, MEDIA_TYPE_EPISODE]

        media_class = fetch_media_class(item)
        children_media_class = media_class
        payload = {
            "title": getattr(item, "name"),
            "media_class": media_class,
            "media_content_id": item.uri,
            "media_content_type": item.type,
            "can_play": item.type in PLAYABLE_MEDIA_TYPES,
            "can_expand": expandable,
            "children_media_class": children_media_class,
        }

        return BrowseMedia(**payload)

    def _media_library_payload(self, media_content_type, media_content_id):
        """ "
        Create response payload to describe contents of a specific library.
        """

        if media_content_type == "root":
            media_content_type = None
            media_content_id = None

        media_class = fetch_media_class(None, MEDIA_CLASS_DIRECTORY)

        library_info = {
            "title": "Mopidy on %s" % self.device_name,
            "media_class": media_class,
            "children_media_class": MEDIA_CLASS_PLAYLIST,
            "media_content_id": "",
            "media_content_type": "root",
            "can_play": False,
            "can_expand": True,
            "children": [],
        }

        _LOGGER.debug("Looking up %s" % media_content_type)
        item_uri = []
        for item in self.client.library.browse(media_content_id):
            library_info["children"].append(self._media_item_payload(item))
            item_uri.append(item.uri)

        # split up the list of images into lists with 50 elements (Mopidy limit)
        s = 10
        uri_set = [
            item_uri[r * s : (r + 1) * s] for r in range((len(item_uri) + s - 1) // s)
        ]
        images = dict()
        for s in uri_set:
            _LOGGER.debug(len(s))
            t = self.client.library.get_images(s)
            _LOGGER.debug(t)
            images.update(t)

        if len(images.keys()) > 0:
            for item in library_info["children"]:
                if (
                    item.media_content_id in images
                    and len(images[item.media_content_id]) > 0
                ):
                    item.thumbnail = images[item.media_content_id][0].uri

        res = BrowseMedia(**library_info)
        res.children_media_class = MEDIA_CLASS_DIRECTORY
        return res


def fetch_media_class(item, default=None):
    """Fetch the media class of a library item"""
    if hasattr(item, "uri"):
        _LOGGER.debug("item uri: %s" % item.uri)

    if hasattr(item, "type"):
        _LOGGER.debug("item type: %s" % item.type)

    if not hasattr(item, "type"):
        return default

    if item is None:
        return default

    uri = item.uri.split(":")
    source = uri[0]

    if item.type == "directory":
        if source == "dleyna":
            media_class = MEDIA_CLASS_URL
        elif source[:7] == "podcast":
            media_class = MEDIA_CLASS_PODCAST
        elif source == "local":
            if "type=album" in item.uri:
                media_class = MEDIA_CLASS_ALBUM
            elif "type=artist&role=composer" in item.uri:
                media_class = MEDIA_CLASS_COMPOSER
            elif "type=genre" in item.uri:
                media_class = MEDIA_CLASS_GENRE
            elif "type=artist" in item.uri:
                media_class = MEDIA_CLASS_ARTIST
            elif "type=track" in item.uri:
                media_class = MEDIA_CLASS_TRACK
            else:
                media_class = MEDIA_CLASS_DIRECTORY
        elif source == "spotify":
            if uri[-1] == "directory":
                media_class = MEDIA_CLASS_MUSIC
            elif uri[-1] in ["playlists", "top", "your"]:
                media_class = MEDIA_CLASS_PLAYLIST
            elif uri[-1] == "artists":
                media_class = MEDIA_CLASS_ARTIST
            elif uri[-1] == "albums":
                media_class = MEDIA_CLASS_ALBUM
            elif uri[-1] == "tracks":
                media_class = MEDIA_CLASS_TRACK
            elif "playlists" in uri:
                media_class = MEDIA_CLASS_PLAYLIST
            else:
                media_class = MEDIA_CLASS_DIRECTORY

        elif source in ["tunein", "somafm", "internetarchive","soundcloud"]:
            media_class = MEDIA_CLASS_URL
        else:
            media_class = MEDIA_CLASS_DIRECTORY

    elif item.type == "track":
        media_class = MEDIA_CLASS_TRACK
    elif item.type == "playlist":
        media_class = MEDIA_CLASS_PLAYLIST
    elif item.type == "album":
        media_class = MEDIA_CLASS_ALBUM
    elif item.type == "artist":
        media_class = MEDIA_CLASS_ARTIST
    else:
        media_class = default
    return media_class
