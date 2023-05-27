"""Support to interact with a MopidyMusic Server."""
import asyncio
import logging
import re

from mopidyapi import MopidyAPI
from requests.exceptions import ConnectionError as reConnectionError
import voluptuous as vol

from homeassistant.components import media_source, spotify

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    BrowseMedia,
    MediaPlayerEntity,
    async_process_play_media_url,
)
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_ALBUM,
    MEDIA_CLASS_ARTIST,
    MEDIA_CLASS_APP,
    MEDIA_CLASS_COMPOSER,
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_GENRE,
    MEDIA_CLASS_MUSIC,
    MEDIA_CLASS_PLAYLIST,
    MEDIA_CLASS_PODCAST,
    MEDIA_CLASS_TRACK,
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
    SUPPORT_SELECT_SOURCE,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_ID,
    CONF_NAME,
    CONF_PORT,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
import homeassistant.util.dt as dt_util

from .const import (
    CACHE_ART,
    CACHE_TITLES,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
    ICON,
    SERVICE_RESTORE,
    SERVICE_SEARCH,
    SERVICE_SNAPSHOT,
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
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_SEEK
    | SUPPORT_STOP
    | SUPPORT_TURN_OFF
    | SUPPORT_TURN_ON
    | SUPPORT_SELECT_SOURCE
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

EXPANDABLE_MEDIA_TYPES = [
    MEDIA_CLASS_ALBUM,
    MEDIA_CLASS_ARTIST,
    MEDIA_CLASS_COMPOSER,
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_GENRE,
    MEDIA_CLASS_MUSIC,
    MEDIA_CLASS_PLAYLIST,
    MEDIA_CLASS_PODCAST,
]

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


def media_source_filter(item: BrowseMedia):
    """Filter media sources."""
    return item.media_content_type.startswith("audio/")


class MissingMediaInformation(BrowseError):
    """Missing media required information."""


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
):
    """Set up the Mopidy platform."""
    uid = config_entry.data[CONF_ID]
    name = config_entry.data[CONF_NAME]
    host = config_entry.data[CONF_HOST]
    port = config_entry.data[CONF_PORT]

    entity = MopidyMediaPlayerEntity(host, port, name, uid)
    async_add_entities([entity])

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(SERVICE_RESTORE, {}, "restore")
    platform.async_register_entity_service(
        SERVICE_SEARCH,
        {
            vol.Optional("exact"): cv.boolean,
            vol.Optional("keyword"): cv.string,
            vol.Optional("keyword_album"): cv.string,
            vol.Optional("keyword_artist"): cv.string,
            vol.Optional("keyword_genre"): cv.string,
            vol.Optional("keyword_track_name"): cv.string,
            vol.Optional("source"): cv.string,
        },
        "search",
    )
    platform.async_register_entity_service(SERVICE_SNAPSHOT, {}, "snapshot")


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

    def __init__(self, hostname, port, name, uuid=None):
        """Initialize the Mopidy device."""
        self.hostname = hostname
        self.port = port
        self.device_name = name
        if uuid is None:
            self.uuid = re.sub(r"[._-]+", "_", self.hostname) + "_" + str(self.port)
        else:
            self.uuid = uuid

        self.server_version = None
        self.supported_uri_schemes = None
        self.player_currenttrack = None
        self.player_streamttile = None
        self.player_currenttrach_source = None

        self._media_position = None
        self._media_position_updated_at = None
        self._state = STATE_UNKNOWN
        self._volume = None
        self._muted = None
        self._media_image_url = None
        self._shuffled = None
        self._repeat_mode = None
        self._playlists = []
        self._currentplaylist = None
        self._tracklist_tracks = None
        self._tracklist_index = None

        self.client = None
        self._available = None

        self._has_support_volume = None

        self._snapshot = None

        self._reset_variables()

    def _reset_variables(self):
        self.server_version = None
        self.supported_uri_schemes = None
        self.player_currenttrack = None
        self.player_streamttile = None
        self.player_currenttrach_source = None

        self._media_position = None
        self._media_position_updated_at = None
        self._state = STATE_UNKNOWN
        self._volume = None
        self._muted = None
        self._media_image_url = None
        self._shuffled = None
        self._repeat_mode = None
        self._playlists = []
        self._currentplaylist = None
        self._tracklist_tracks = None
        self._tracklist_index = None

        self.client = None
        self._available = None

        self._has_support_volume = None

        self._snapshot = None

    def _fetch_status(self):
        """Fetch status from Mopidy."""
        _LOGGER.debug("Fetching Mopidy Server status for %s", self.device_name)
        try:
            self.player_currenttrack = self.client.playback.get_current_track()
        except reConnectionError:
            self._reset_variables()
            self._state = STATE_UNAVAILABLE
            return

        self.player_streamttile = self.client.playback.get_stream_title()
        self.supported_uri_schemes = self.client.rpc_call("core.get_uri_schemes")

        if hasattr(self.player_currenttrack, "uri"):
            self.player_currenttrach_source = self.player_currenttrack.uri.partition(
                ":"
            )[0]
        else:
            self.player_currenttrach_source = None

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
            self._state = STATE_OFF
        else:
            self._state = STATE_UNKNOWN

        volume = self.client.mixer.get_volume()
        self._volume = None
        self._has_support_volume = False
        if volume is not None:
            self._volume = float(volume / 100)
            self._has_support_volume = True

        self._muted = self.client.mixer.get_mute()

        if hasattr(self.player_currenttrack, "uri"):
            res = self.client.library.get_images([self.player_currenttrack.uri])
            if (
                self.player_currenttrack.uri in res
                and len(res[self.player_currenttrack.uri]) > 0
                and hasattr(res[self.player_currenttrack.uri][0], "uri")
            ):
                self._media_image_url = res[self.player_currenttrack.uri][0].uri
                if self.player_currenttrach_source == "local":
                    self._media_image_url = (
                        f"http://{self.hostname}:{self.port}{self._media_image_url}"
                    )
        else:
            self._media_image_url = None

        self._shuffled = self.client.tracklist.get_random()
        self._playlists = self.client.playlists.as_list()

        repeat = self.client.tracklist.get_repeat()
        single = self.client.tracklist.get_single()
        if repeat and single:
            self._repeat_mode = REPEAT_MODE_ONE
        elif repeat:
            self._repeat_mode = REPEAT_MODE_ALL
        else:
            self._repeat_mode = REPEAT_MODE_OFF

        self._tracklist_tracks = [t.uri for t in self.client.tracklist.get_tracks()]
        self._tracklist_index = self.client.tracklist.index()

    def search(self, **kwargs):
        """Search the Mopidy Server media library."""
        query = {}
        uris = None
        if isinstance(kwargs.get("keyword"), str):
            query["any"] = [kwargs["keyword"].strip()]

        if isinstance(kwargs.get("keyword_album"), str):
            query["album"] = [kwargs["keyword_album"].strip()]

        if isinstance(kwargs.get("keyword_artist"), str):
            query["artist"] = [kwargs["keyword_artist"].strip()]

        if isinstance(kwargs.get("keyword_genre"), str):
            query["genre"] = [kwargs["keyword_genre"].strip()]

        if isinstance(kwargs.get("keyword_track_name"), str):
            query["track_name"] = [kwargs["keyword_track_name"].strip()]

        if len(query.keys()) == 0:
            return

        if isinstance(kwargs.get("source"), str):
            uris = []
            for source in kwargs["source"].split(","):
                if source.partition(":")[1] == "":
                    source = source + ":"
                if source.partition(":")[0] in self.supported_uri_schemes:
                    uris.append(source)
            if len(uris) == 0:
                uris = None

        search = self.client.library.search(
            query=query, uris=uris, exact=kwargs.get("exact", False)
        )
        track_uris = []
        for result in search:
            for track in getattr(result, "tracks", []):
                track_uris.append(track.uri)

        if len(track_uris) == 0:
            return

        self.client.tracklist.add(uris=track_uris)

    def snapshot(self):
        """Make a snapshot of Mopidy Server."""
        self._fetch_status()
        self._snapshot = {
            "mediaposition": self._media_position,
            "muted": self._muted,
            "repeat_mode": self._repeat_mode,
            "shuffled": self._shuffled,
            "state": self._state,
            "tracklist": self._tracklist_tracks,
            "tracklist_index": self._tracklist_index,
            "volume": self._volume,
        }

    def restore(self):
        """Restore Mopidy Server snapshot."""
        if self._snapshot is None:
            return
        self.media_stop()
        self.clear_playlist()
        self.client.tracklist.add(uris=self._snapshot["tracklist"])

        if self._snapshot["state"] == STATE_OFF:
            self.turn_off()
            self.set_volume_level(self._snapshot["volume"])
            self.mute_volume(self._snapshot["muted"])
            self.set_repeat(self._snapshot["repeat_mode"])
            self.set_shuffle(self._snapshot["shuffled"])

            self._snapshot = None

        elif self._snapshot["state"] in [STATE_PLAYING, STATE_PAUSED]:
            self.client.playback.play(
                tlid=getattr(
                    self.client.tracklist.get_tl_tracks()[
                        self._snapshot["tracklist_index"]
                    ],
                    "tlid",
                )
            )
            self.restore_onplay()

    async def restore_onplay(self):
        if self.client.playback.get_state() == "playing":
            _LOGGER.info("Finally, the player is playing")
            if self._snapshot["mediaposition"] > 0:
                self.media_seek(self._snapshot["mediaposition"])

            if self._snapshot["state"] == STATE_PAUSED:
                self.media_pause()

            self.set_volume_level(self._snapshot["volume"])
            self.mute_volume(self._snapshot["muted"])
            self.set_repeat(self._snapshot["repeat_mode"])
            self.set_shuffle(self._snapshot["shuffled"])

            self._snapshot = None
        else:
            _LOGGER.info("waiting for player to actually start playing")
            await asyncio.sleep(1)

    @property
    def unique_id(self):
        """Return the unique id for the entity."""
        return self.uuid

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
        if self.player_streamttile is not None:
            return self.player_streamttile

        if hasattr(self.player_currenttrack, "name"):
            return self.player_currenttrack.name
        return None

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        if self.player_streamttile is not None:
            if hasattr(self.player_currenttrack, "name"):
                return self.player_currenttrack.name

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
        if self._currentplaylist is not None:
            return self._currentplaylist

        if hasattr(self.player_currenttrack, "album") and hasattr(
            self.player_currenttrack.album, "name"
        ):
            return self.player_currenttrack.album.name

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
        support = SUPPORT_MOPIDY
        if self._has_support_volume:
            support = (
                support | SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_STEP
            )
        return support

    @property
    def source(self):
        """Name of the current input source."""
        return None

    @property
    def source_list(self):
        """Return the list of available input sources."""
        return sorted([el.name for el in self._playlists])

    def mute_volume(self, mute):
        """Mute the volume."""
        self.client.mixer.set_mute(mute)

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self.client.mixer.set_volume(int(volume * 100))

    def turn_off(self):
        """Turn the media player off."""
        self.client.playback.stop()

    def turn_on(self):
        """Turn the media player on."""
        self.client.playback.play()
        self._fetch_status()

    def media_play(self):
        """Send play command."""
        self.client.playback.play()
        self._fetch_status()

    def media_pause(self):
        """Send pause command."""
        self.client.playback.pause()
        self._fetch_status()

    def media_stop(self):
        """Send stop command."""
        self.client.playback.stop()
        self._fetch_status()

    def media_previous_track(self):
        """Send previous track command."""
        self.client.playback.previous()
        self._fetch_status()

    def media_next_track(self):
        """Send next track command."""
        self.client.playback.next()  # pylint: disable=not-callable
        self._fetch_status()

    def media_seek(self, position):
        """Send seek command."""
        self.client.playback.seek(int(position * 1000))
        self._fetch_status()

    def play_media(self, media_type, media_id, **kwargs):
        """Play a piece of media."""
        self._currentplaylist = None

        if media_source.is_media_source_id(media_id):
            sourced_media = asyncio.run_coroutine_threadsafe(
                media_source.async_resolve_media(self.hass, media_id), self.hass.loop
            ).result()
            media_type = sourced_media.mime_type
            media_id = async_process_play_media_url(self.hass, sourced_media.url)
            media_uris = [media_id]
        elif spotify.is_spotify_media_type(media_type):
            media_type = spotify.resolve_spotify_media_type(media_type)
            media_id = spotify.spotify_uri_from_media_browser_url(media_id)
            media_uris = [media_id]
        elif media_type == MEDIA_CLASS_PLAYLIST:
            playlist = self.client.playlists.lookup(media_id)
            self._currentplaylist = playlist.name
            if media_id.partition(":")[0] == "m3u":
                media_uris = [t.uri for t in playlist.tracks]
            else:
                media_uris = [media_id]
        elif media_type == MEDIA_CLASS_DIRECTORY:
            media_uris = [ el.uri for el in self.client.library.browse(media_id) ]
        else:
            media_uris = [media_id]

        t_uris = []
        schemes = self.client.rpc_call("core.get_uri_schemes")
        for uri in media_uris:
            if "yt" in schemes and (
                uri.startswith("https://www.youtube.com/")
                or uri.startswith("https://youtube.com/")
                or uri.startswith("https://youtu.be/")
            ):
                t_uris.append(f"yt:{uri}")
            else:
                t_uris.append(uri)

        media_uris = t_uris

        if len(media_uris) > 0:
            self.client.tracklist.clear()
            self.client.tracklist.add(uris=media_uris)
            self.client.playback.play()

        else:
            _LOGGER.error("No media for %s (%s) could be found.", media_id, media_type)
            raise MissingMediaInformation
        self._fetch_status()

    def select_source(self, source):
        """Select input source."""
        for playlist in self._playlists:
            if playlist.name == source:
                self.play_media(MEDIA_TYPE_PLAYLIST, playlist.uri)
                return playlist.uri
        raise ValueError(f"Could not find {source}")
        self._fetch_status()

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
        """Return the device class."""
        return "speaker"

    @property
    def device_info(self):
        """Return device information about this entity."""
        return {
            "indentifiers": {(DOMAIN, self.device_name)},
            "manufacturer": "Mopidy",
            "model": f"Mopidy server {self.server_version}",
            "name": self.device_name,
            "sw_version": self.server_version,
        }

    def _connect(self):
        try:
            self.client = MopidyAPI(
                host=self.hostname,
                port=self.port,
                use_websocket=False,
                logger=logging.getLogger(__name__ + ".client"),
            )
            self.server_version = self.client.rpc_call("core.get_version")
            _LOGGER.debug(
                "Connection to Mopidy server %s (%s:%s) established",
                self.device_name,
                self.hostname,
                self.port,
            )
        except reConnectionError as error:
            _LOGGER.error(
                "Cannot connect to %s @ %s:%s",
                self.device_name,
                self.hostname,
                self.port,
            )
            _LOGGER.error(error)
            self._available = False
            return
        self._available = True

    def update(self):
        """Get the latest data and update the state."""
        if not self._available:
            self._connect()

        if self._available:
            self._fetch_status()

    async def async_browse_media(
        self,
        media_content_type=None,
        media_content_id=None,
    ):
        _LOGGER.debug(
            "async_browse_media(%s, %s)", media_content_type, media_content_id
        )

        if media_content_id is None:
            return await self.root_payload()

        if media_source.is_media_source_id(media_content_id):
            return await media_source.async_browse_media(
                self.hass, media_content_id, content_filter=media_source_filter
            )

        if spotify.is_spotify_media_type(media_content_type):
            return await spotify.async_browse_media(
                self.hass, media_content_type, media_content_id, can_play_artist=False
            )

        return await self.hass.async_add_executor_job(
            self._media_library_payload,
            {
                "media_content_type": media_content_type,
                "media_content_id": media_content_id,
            },
        )

    async def root_payload(self):
        """Return root payload for Mopidy."""
        children = [
            BrowseMedia(
                title="Mopidy",
                media_class=MEDIA_CLASS_APP,
                media_content_id="library",
                media_content_type="library",
                can_play=False,
                can_expand=True,
                thumbnail="https://brands.home-assistant.io/_/mopidy/logo.png",
            )
        ]

        # If we have spotify both in mopidy and HA, show the HA component
        lib = await self.hass.async_add_executor_job(self.client.library.browse, None)
        for item in lib:
            if getattr(item, "uri") == "spotify:directory" and "spotify" in self.hass.config.components:
                result = await spotify.async_browse_media(self.hass, None, None)
                children.extend(result.children)
                break

        try:
            item = await media_source.async_browse_media(
                self.hass, None, content_filter=media_source_filter
            )
            # If domain is None, it's overview of available sources
            if item.domain is None:
                children.extend(item.children)
            else:
                children.append(item)
        except media_source.BrowseError:
            pass

        if len(children) == 1:
            return await self.async_browse_media(
                children[0].media_content_type,
                children[0].media_content_id,
            )

        return BrowseMedia(
            title="Mopidy",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_id="",
            media_content_type="root",
            can_play=False,
            can_expand=True,
            children=children,
        )

    def _media_item_image_url(self, source, url):
        """Return the correct url to the item's thumbnail."""
        if source == "local":
            url = f"http://{self.hostname}:{self.port}{url}"

        url = f"{url}?t=x"
        return url

    def _media_library_payload(self, payload):
        """Create response payload to describe contents of a specific library."""
        _image_uris = []

        if (
            payload.get("media_content_type") is None
            or payload.get("media_content_id") is None
        ):
            _LOGGER.error("Missing type or uri for media item payload: %s", payload)
            raise MissingMediaInformation

        library_info, mopidy_info = get_media_info(payload)
        if mopidy_info["art_uri"] != "library":
            if mopidy_info["art_uri"] not in CACHE_ART:
                _image_uris.append(mopidy_info["art_uri"])

        library_children = {}
        for path in self.client.library.browse(mopidy_info["browsepath"]):
            library_children[getattr(path, "uri")] = dict(
                zip(
                    ("library_info", "mopidy_info"),
                    get_media_info(
                        {
                            "media_content_type": getattr(path, "type", "directory"),
                            "media_content_id": getattr(path, "uri"),
                            "name": getattr(path, "name", "unknown"),
                        }
                    ),
                )
            )
            if (
                library_children[getattr(path, "uri")]["mopidy_info"] is not None
                and library_children[getattr(path, "uri")]["mopidy_info"]["art_uri"]
                not in CACHE_ART
            ):
                _image_uris.append(
                    library_children[getattr(path, "uri")]["mopidy_info"]["art_uri"]
                )

        if mopidy_info["source"] == "spotify":
            # Spotify thumbnail lookup is throttled
            pagesize = 10
        else:
            pagesize = 1000
        uri_sets = [
            _image_uris[r * pagesize : (r + 1) * pagesize]
            for r in range((len(_image_uris) + pagesize - 1) // pagesize)
        ]

        for uri_set in uri_sets:
            if len(uri_set) == 0:
                continue
            i = self.client.library.get_images(uri_set)
            for img_uri in i:
                if len(i[img_uri]) > 0:
                    CACHE_ART[img_uri] = self._media_item_image_url(
                        mopidy_info["source"], i[img_uri][0].uri
                    )
                else:
                    CACHE_ART[img_uri] = None

        if (
            mopidy_info["art_uri"] in CACHE_ART
            and CACHE_ART[mopidy_info["art_uri"]] is not None
        ):
            library_info["thumbnail"] = CACHE_ART[mopidy_info["art_uri"]]

        for i in library_children:
            if (
                library_children[i]["mopidy_info"] is not None
                and library_children[i]["mopidy_info"]["art_uri"] in CACHE_ART
                and CACHE_ART[library_children[i]["mopidy_info"]["art_uri"]] is not None
            ):
                library_children[i]["library_info"]["thumbnail"] = CACHE_ART[
                    library_children[i]["mopidy_info"]["art_uri"]
                ]

        library_info["children"] = [
            BrowseMedia(**library_children[c]["library_info"])
            for c in library_children
            if library_children[c]["library_info"] is not None
        ]
        return BrowseMedia(**library_info)


def get_media_info(info):
    """Build Library object."""
    disabled_uris = ["local:directory?type=track"]
    if info["media_content_id"] in CACHE_TITLES:
        info["name"] = CACHE_TITLES[info["media_content_id"]]

    library_info = {
        "children": [],
        "media_class": info["media_content_type"],
        "media_content_id": info["media_content_id"],
        "media_content_type": info["media_content_type"],
        "title": info.get("name", "Unknown"),
        "can_play": info.get("media_content_type", MEDIA_CLASS_DIRECTORY)
        in PLAYABLE_MEDIA_TYPES,
        "can_expand": info.get("media_content_type", MEDIA_CLASS_DIRECTORY)
        in EXPANDABLE_MEDIA_TYPES,
    }
    mopidy_info = {
        "browsepath": info.get("media_content_id"),
        "art_uri": info.get("media_content_id"),
        "source": info.get("media_content_id").partition(":")[0],
    }

    source = info.get("media_content_id").partition(":")[0]
    uri = info.get("media_content_id").partition(":")[2]

    if info["media_content_id"] in disabled_uris:
        return None, None

    if info["media_content_id"] == "library":
        library_info.update(
            {
                "title": "Media Library",
                "can_expand": True,
            }
        )
        mopidy_info["browsepath"] = None

    if source == "local":
        media_info = {}
        for uri_info in uri.partition("?")[2].split("&"):
            if uri_info != "":
                media_info[uri_info.partition("=")[0]] = uri_info.partition("=")[2]
        if media_info.get("type") == "album":
            library_info["media_class"] = MEDIA_CLASS_ALBUM
        elif media_info.get("type") == "artist":
            library_info["media_class"] = MEDIA_CLASS_ARTIST
        elif media_info.get("type") == "genre":
            library_info["media_class"] = MEDIA_CLASS_GENRE
        elif media_info.get("type") == "track":
            library_info["media_class"] = MEDIA_CLASS_TRACK

        if media_info.get("album") is not None:
            mopidy_info["art_uri"] = media_info["album"]
            library_info["can_play"] = True
            library_info["media_class"] = MEDIA_CLASS_ALBUM
        elif media_info.get("genre") is not None:
            library_info["media_class"] = MEDIA_CLASS_GENRE

        if (
            media_info.get("role") is not None
            and media_info["role"] == "composer"
            or media_info.get("composer") is not None
        ):
            library_info["media_class"] = MEDIA_CLASS_COMPOSER

    elif source == "spotify":
        if (
            "spotify:top:albums" in info["media_content_id"]
            or "spotify:your:albums" in info["media_content_id"]
        ):
            library_info["media_class"] = MEDIA_CLASS_ALBUM
        elif "spotify:top:artists" in info["media_content_id"]:
            library_info["media_class"] = MEDIA_CLASS_ARTIST
        elif (
            "spotify:top:tracks" in info["media_content_id"]
            or "spotify:your:tracks" in info["media_content_id"]
        ):
            library_info["media_class"] = MEDIA_CLASS_TRACK
        elif "spotify:playlists" in info["media_content_id"]:
            library_info["media_class"] = MEDIA_CLASS_PLAYLIST

    elif "podcast+" in source:
        library_info["media_class"] = MEDIA_CLASS_PODCAST

    elif source == "tunein":
        media_info = library_info["media_content_id"].split(":")
        library_info["media_class"] = MEDIA_CLASS_DIRECTORY

    CACHE_TITLES[info["media_content_id"]] = library_info["title"]
    return library_info, mopidy_info
