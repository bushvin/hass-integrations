"""Support to interact with a MopidyMusic Server."""
import asyncio
import logging
from functools import partial
import re
import time
import urllib.parse as urlparse
from typing import Any
import datetime as dt

import urllib.parse as urlparse
from urllib.parse import parse_qs

from mopidyapi import MopidyAPI
from requests.exceptions import ConnectionError as reConnectionError
import voluptuous as vol

from homeassistant.components import media_source, spotify

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    BrowseMedia,
    MediaClass,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
    async_process_play_media_url,
)

from homeassistant.components.media_player.errors import BrowseError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_ID,
    CONF_NAME,
    CONF_PORT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
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
    SERVICE_GET_SEARCH_RESULT,
    SERVICE_SNAPSHOT,
    SERVICE_SET_CONSUME_MODE,
    YOUTUBE_URLS,
)

from .speaker import (
    MopidyLibrary,
    MopidySpeaker,
)

PLAYABLE_MEDIA_TYPES = [
    MediaType.ALBUM,
    MediaType.ARTIST,
    MediaType.EPISODE,
    MediaType.TRACK,
]

EXPANDABLE_MEDIA_TYPES = [
    MediaClass.ALBUM,
    MediaClass.ARTIST,
    MediaClass.COMPOSER,
    MediaClass.DIRECTORY,
    MediaClass.GENRE,
    MediaClass.MUSIC,
    MediaClass.PLAYLIST,
    MediaClass.PODCAST,
]

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)

SEARCH_SCHEMA = {
    vol.Optional("exact"): cv.boolean,
    vol.Optional("keyword"): cv.string,
    vol.Optional("keyword_album"): cv.string,
    vol.Optional("keyword_artist"): cv.string,
    vol.Optional("keyword_genre"): cv.string,
    vol.Optional("keyword_track_name"): cv.string,
    vol.Optional("source"): cv.string,
}


def media_source_filter(item: BrowseMedia):
    """Filter media sources."""
    return item.media_content_type.startswith("audio/")


class MissingMediaInformation(BrowseError):
    """Missing media required information."""

class MissingMopidyExtension(BrowseError):
    """Missing Mopidy Extension."""

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up the Mopidy platform."""
    device_uuid = config_entry.data[CONF_ID]
    device_name = config_entry.data[CONF_NAME]
    hostname = config_entry.data[CONF_HOST]
    port = config_entry.data[CONF_PORT]

    speaker = MopidySpeaker(hass, hostname, port)
    entity = MopidyMediaPlayerEntity(speaker, device_name, device_uuid)
    async_add_entities([entity])

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(SERVICE_RESTORE, {}, "service_restore")
    platform.async_register_entity_service(
        SERVICE_SEARCH,
        SEARCH_SCHEMA,
        "service_search",
    )
    platform.async_register_entity_service(
        SERVICE_GET_SEARCH_RESULT,
        SEARCH_SCHEMA,
        "service_get_search_result",
        supports_response=SupportsResponse.ONLY,
    )
    platform.async_register_entity_service(SERVICE_SNAPSHOT, {}, "service_snapshot")
    platform.async_register_entity_service(
        SERVICE_SET_CONSUME_MODE,
        {vol.Required("consume_mode", default=False): cv.boolean},
        "service_set_consume_mode",
    )

# NOTE: Is this still needed?
async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discover_info=None
):
    """Set up the Mopidy platform."""
    device_name = config.get(CONF_NAME)
    hostname = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    speaker = MopidySpeaker(hass, hostname, port)
    entity = MopidyMediaPlayerEntity(speaker, device_name)
    async_add_entities([entity], True)


class MopidyMediaPlayerEntity(MediaPlayerEntity):
    """Representation of the Mopidy server."""

    _attr_name = None
    _attr_media_content_type = MediaType.MUSIC
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER

    _attr_consume_mode: bool | None = None
    speaker: MopidySpeaker | None = None

    def __init__(self, speaker, device_name, device_uuid=None) -> None:
        """Initialize the Mopidy device."""

        self.speaker = speaker
        self.speaker.entity = self
        self.device_name = device_name

        if device_uuid is None:
            self.device_uuid = re.sub(r"[._-]+", "_", self.speaker.hostname) + "_" + str(self.speaker.port)
        else:
            self.device_uuid = device_uuid

    def is_youtube_media_type(self, media_id):
        """Check if the provided is a youtube resource"""
        url = urlparse.urlparse(media_id)
        if len([ x for x in YOUTUBE_URLS if url.netloc.lower().endswith(x.lower()) ]) > 0:
            return True
        else:
            return False

    def resolve_youtube_media_type(self, media_type):
        """Return the media type for youtube videos"""
        return MediaType.MUSIC

    def youtube_uri_from_media_id(self, media_id):
        """Parse the youtube media_id and return a usable resource"""
        url = urlparse.urlparse(media_id)
        if "youtube" in self.speaker.supported_uri_schemes:
            query_parsed = parse_qs(url.query)
            media_id = f"youtube:video:{query_parsed['v'][0]}"

        elif "yt" in self.speaker.supported_uri_schemes:
            media_id = f"yt:{media_id}"

        else:
            raise MissingMopidyExtension("No Mopidy Extensions found for Youtube. If this incorrect, please open an issue.")

        return media_id

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play provided media_id"""

        if self.is_youtube_media_type(media_id):
            media_type = self.resolve_youtube_media_type(media_type)
            media_id = self.youtube_uri_from_media_id(media_id)

        if media_source.is_media_source_id(media_id):

            media_type = MediaType.MUSIC
            media = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = async_process_play_media_url(self.hass, media.url)

        if spotify.is_spotify_media_type(media_type):
            media_type = spotify.resolve_spotify_media_type(media_type)
            media_id = spotify.spotify_uri_from_media_browser_url(media_id)


        await self.hass.async_add_executor_job(
            partial(self.speaker.play_media , media_type, media_id, **kwargs)
        )

    def force_update_ha_state(self):
        self.schedule_update_ha_state(force_refresh=True)

    def clear_playlist(self) -> None:
        """Clear players playlist."""
        self.speaker.clear_queue()

    def media_next_track(self) -> None:
        """Send next track command."""
        self.speaker.media_next_track()

    def media_pause(self) -> None:
        """Send pause command."""
        self.speaker.media_pause()

    def media_play(self) -> None:
        """Send play command."""
        self.speaker.media_play()

    def media_previous_track(self) -> None:
        """Send previous track command."""
        self.speaker.media_previous_track()

    def media_seek(self, position) -> None:
        """Send seek command."""
        self.speaker.media_seek(int(position * 1000))

    def media_stop(self) -> None:
        """Send stop command."""
        self.speaker.media_stop()

    def mute_volume(self, mute) -> None:
        """Mute the volume."""
        self.speaker.set_mute(mute)

    def select_source(self, source) -> None:
        """Select input source."""
        self.speaker.select_source(source)

    def service_restore(self) -> None:
        """Restore Mopidy Server snapshot."""
        self.speaker.restore_snapshot()

    def service_search(self, **kwargs) -> None:
        """Search the Mopidy Server media library."""
        self.speaker.queue_tracks(
            self._search(**kwargs)
        )

    def service_get_search_result(self, **kwargs) -> dict:
        return {'result': self._search(**kwargs)}

    def _search(self, **kwargs) -> dict:
        query = {}
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
            return {'result': {}}

        sources = []
        if isinstance(kwargs.get("source"), str):
            sources = kwargs["source"].split(",")

        return self.library.search_tracks(sources, query, kwargs.get("exact", False))

    def service_set_consume_mode(self, **kwargs) -> None:
        """Set/Unset Consume mode"""
        self.speaker.set_consume_mode(kwargs.get("consume_mode", False))

    def service_snapshot(self) -> None:
        """Make a snapshot of Mopidy Server."""
        self.speaker.take_snapshot()

    def set_repeat(self, repeat) -> None:
        """Set repeat mode."""
        self.speaker.set_repeat_mode(repeat)

    def set_shuffle(self, shuffle) -> None:
        """Enable/disable shuffle mode."""
        self.speaker.set_shuffle(shuffle)

    def set_volume_level(self, volume) -> None:
        """Set volume level, range 0..1."""
        self.speaker.set_volume(int(volume * 100))

    def volume_down(self) -> None:
        """Turn volume down for media player."""
        self.speaker.volume_down()

    def volume_up(self) -> None:
        """Turn volume up for media player."""
        self.speaker.volume_up()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.speaker.is_available

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information about this entity."""
        return {
            "identifiers": {(DOMAIN, self.device_name)},
            "manufacturer": "Mopidy",
            "model": f"Mopidy server {self.speaker.software_version}",
            "name": self.device_name,
            "sw_version": self.speaker.software_version,
        }

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes"""
        attributes: dict[str, Any] = {}

        if self.speaker.consume_mode is not None:
            attributes["consume_mode"] = self.speaker.consume_mode

        if self.speaker.queue.current_track_extension is not None:
            attributes["mopidy_extension"] = self.speaker.queue.current_track_extension

        if self.speaker.queue.position is not None:
            attributes["queue_position"] = self.speaker.queue.position

        if self.speaker.queue.size is not None:
            attributes["queue_size"] = self.speaker.queue.size

        if self.speaker.snapshot_taken_at is not None:
            attributes["snapshot_taken_at"] = self.speaker.snapshot_taken_at

        return attributes

    @property
    def icon(self) -> str:
        """Return the icon."""
        return ICON

    @property
    def library(self) -> MopidyLibrary:
        """Return the library object from the speaker"""
        return self.speaker.library

    # @property
    # def media(self) -> MopidyMedia:
    #     """Return the media object from the speaker"""
    #     return self.speaker.media

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self.device_name

    @property
    def state(self) -> MediaPlayerState | None:
        """State of the player."""
        if self.speaker is None:
            return None
        else:
            return self.speaker.state

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        if self.speaker is None:
            return None
        elif self.speaker.volume_level is None:
            return None
        else:
            return float(self.speaker.volume_level/100)

    @property
    def is_volume_muted(self) -> bool | None:
        """Boolean if volume is currently muted."""
        if self.speaker is None:
            return None
        else:
            return self.speaker.is_muted

    @property
    def media_content_id(self) -> str | None:
        """Content ID of current playing media."""
        return self.speaker.queue.current_track_uri

    @property
    def media_content_type(self) -> MediaType | str | None:
        """Content type of current playing media."""
        return self._attr_media_content_type

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        return self.speaker.queue.current_track_duration

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        return self.speaker.queue.current_track_position

    @property
    def media_position_updated_at(self) -> dt.datetime | None:
        """When was the position of the current playing media valid.

        Returns value from homeassistant.util.dt.utcnow().
        """
        return self.speaker.queue.current_track_position_updated_at

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        return self.speaker.queue.current_track_image_url

    @property
    def media_image_remotely_accessible(self) -> bool:
        """If the image url is remotely accessible."""
        return self.speaker.queue.current_track_image_remotely_accessible

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        return self.speaker.queue.current_track_title

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        return self.speaker.queue.current_track_artist

    @property
    def media_album_name(self) -> str | None:
        """Album name of current playing media, music track only."""
        return self.speaker.queue.current_track_album_name

    @property
    def media_album_artist(self) -> str | None:
        """Album artist of current playing media, music track only."""
        return self.speaker.queue.current_track_album_artist

    @property
    def media_track(self) -> int | None:
        """Track number of current playing media, music track only."""
        return self.speaker.queue.current_track_number

    @property
    def media_playlist(self) -> str | None:
        """Title of Playlist currently playing."""
        return self.speaker.queue.current_track_playlist_name

    @property
    def source(self) -> str | None:
        """Name of the current input source."""
        # FIXME: DO we need to look at this?
        return self._attr_source

    @property
    def source_list(self) -> list[str] | None:
        """List of available input sources."""
        if self.speaker is None:
            return None
        else:
            return self.speaker.source_list

    @property
    def shuffle(self) -> bool | None:
        """Boolean if shuffle is enabled."""
        if self.speaker is None:
            return None
        else:
            return self.speaker.is_shuffled

    @property
    def repeat(self) -> RepeatMode | str | None:
        """Return current repeat mode."""
        if self.speaker is None:
            return None
        else:
            return self.speaker.repeat

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        if self.speaker is None:
            return None
        else:
            return self.speaker.features

    @property
    def unique_id(self) -> str:
        """Return the unique id for the entity."""
        return self.device_uuid

    def update(self) -> None:
        """Get the latest data and update the state."""

        self.speaker.update()

        if self.state is None:
            _LOGGER.error(f"{self.entity_id} is unavailable")
            return

    async def async_browse_media(
        self,
        media_content_type=None,
        media_content_id=None,
    ) -> None:

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

    async def root_payload(self) -> dict[str, Any]:
        """Return root payload for Mopidy."""
        children = [
            BrowseMedia(
                title="Mopidy",
                media_class=MediaClass.APP,
                media_content_id="library",
                media_content_type="library",
                can_play=False,
                can_expand=True,
                thumbnail="https://brands.home-assistant.io/_/mopidy/logo.png",
            )
        ]

        # If we have spotify both in mopidy and HA, show the HA component
        lib = await self.hass.async_add_executor_job(self.library.browse, None)
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
            media_class=MediaClass.DIRECTORY,
            media_content_id="",
            media_content_type="root",
            can_play=False,
            can_expand=True,
            children=children,
        )

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
        for path in self.library.browse(mopidy_info["browsepath"]):
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
            i = self.library.get_images(uri_set)
            for img_uri in i:
                if len(i[img_uri]) > 0:
                    CACHE_ART[img_uri] = self.speaker.queue.expand_url(mopidy_info["source"], i[img_uri][0].uri)
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
        "can_play": info.get("media_content_type", MediaClass.DIRECTORY)
        in PLAYABLE_MEDIA_TYPES,
        "can_expand": info.get("media_content_type", MediaClass.DIRECTORY)
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
            library_info["media_class"] = MediaClass.ALBUM
        elif media_info.get("type") == "artist":
            library_info["media_class"] = MediaClass.ARTIST
        elif media_info.get("type") == "genre":
            library_info["media_class"] = MediaClass.GENRE
        elif media_info.get("type") == "track":
            library_info["media_class"] = MediaClass.TRACK

        if media_info.get("album") is not None:
            mopidy_info["art_uri"] = media_info["album"]
            library_info["can_play"] = True
            library_info["media_class"] = MediaClass.ALBUM
        elif media_info.get("genre") is not None:
            library_info["media_class"] = MediaClass.GENRE

        if (
            media_info.get("role") is not None
            and media_info["role"] == "composer"
            or media_info.get("composer") is not None
        ):
            library_info["media_class"] = MediaClass.COMPOSER

    elif source == "spotify":
        if (
            "spotify:top:albums" in info["media_content_id"]
            or "spotify:your:albums" in info["media_content_id"]
        ):
            library_info["media_class"] = MediaClass.ALBUM
        elif "spotify:top:artists" in info["media_content_id"]:
            library_info["media_class"] = MediaClass.ARTIST
        elif (
            "spotify:top:tracks" in info["media_content_id"]
            or "spotify:your:tracks" in info["media_content_id"]
        ):
            library_info["media_class"] = MediaClass.TRACK
        elif "spotify:playlists" in info["media_content_id"]:
            library_info["media_class"] = MediaClass.PLAYLIST

    elif "podcast+" in source:
        library_info["media_class"] = MediaClass.PODCAST

    elif source == "tunein":
        media_info = library_info["media_content_id"].split(":")
        library_info["media_class"] = MediaClass.DIRECTORY

    CACHE_TITLES[info["media_content_id"]] = library_info["title"]
    return library_info, mopidy_info
