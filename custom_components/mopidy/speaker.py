"""Base class for common mopidy speaker tasks.."""
import logging
#import asyncio
import datetime
import time
from mopidyapi import MopidyAPI
import urllib.parse as urlparse
from urllib.parse import urlencode

from homeassistant.components import media_source, spotify
from homeassistant.core import HomeAssistant
from homeassistant.components.media_player import (
    ATTR_MEDIA_ENQUEUE,
    async_process_play_media_url,
    MediaClass,
    MediaPlayerEnqueue,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.components.media_player.errors import BrowseError
import homeassistant.util.dt as dt_util
from requests.exceptions import ConnectionError as reConnectionError

from .const import (
    DEFAULT_PORT,
)

_LOGGER = logging.getLogger(__name__)

class MissingMediaInformation(BrowseError):
    """Missing media required information."""

class MopidyLibrary:
    """Representation of the current Mopidy media."""

    api: MopidyAPI | None = None
    _attr_supported_uri_schemes: list | None = None

    def browse(self, uri=None):
        """Wrapper for the MopidyAPI.library.browse method"""
        # NOTE: when uri is None, the root will be returned
        return self.api.library.browse(uri)

    def get_images(self, uris=None):
        """Wrapper for the MopidyAPI.library.get_images method"""
        if uris is None:
            # TODO: return error
            return

        return self.api.library.get_images(uris)

    def get_playlist(self, uri=None):
        return self.api.playlists.lookup(uri)

    def get_playlist_track_uris(self, uri=None):
        if uri.partition(":")[0] == "m3u":
            return [x.uri for x in self.get_playlist(uri).tracks]

        return [x.uri for x in self.browse(uri)]

    @property
    def playlists(self):
        """Return playlists known to mopidy"""
        # NOTE: check if we need to/can extend the playlist entries with MediaType
        # ret = []
        # for el in self.api.playlists.as_list():
        #     el["media_type"] = MediaType.PLAYLIST
        #     ret.append(el)
        if not hasattr(self.api, "playlists"):
            return []
        return self.api.playlists.as_list()

    def search(self, sources=None, query=None, exact=False):
        """Search the library for something"""

        if sources is None:
            sources = []

        uris = []

        for el in sources:
            if el.partition(":")[1] == "":
                el = "%s:" % el
            if el.partition(":")[0] in self.supported_uri_schemes:
                uris.append(el)

        if len(uris) == 0:
            uris = None

        res = self.api.library.search(
            query=query,
            uris=uris,
            exact=exact,
        )
        return res

    def search_tracks(self, sources=None, query=None, exact=False):
        """Search the library for matching tracks"""
        uris = []
        for res in self.search(sources, query, exact):
            for track in getattr(res, "tracks", []):
                uris.append(track.uri)

        return uris

    @property
    def supported_uri_schemes(self):
        if self._attr_supported_uri_schemes is None:
            self._attr_supported_uri_schemes = self.api.rpc_call("core.get_uri_schemes")

        return self._attr_supported_uri_schemes

class MopidyMedia:
    api: MopidyAPI | None = None

    _attr_local_url_base: str | None = None
    _attr_track_uri: str | None = None
    _attr_track_source: str | None = None
    _attr_track_number: int | None = None
    _attr_track_duration: int | None = None
    _attr_media_title: str | None = None
    _attr_media_artist: str | None = None
    _attr_media_position: int | None = None
    _attr_media_position_updated_at: datetime.datetime | None = None
    _attr_album_name: str | None = None
    _attr_album_artist: str | None = None
    _attr_playlist_name: str | None = None
    _playlist_track_uris: list | None = None
    _attr_media_image_url: str | None = None
    _attr_is_stream: bool | None = None
    _attr_extension: str | None = None

    def __init__(self):
        self.clear()

    def clear(self):
        self._attr_track_uri = None
        self._attr_track_source = None
        self._attr_track_number = None
        self._attr_track_duration = None
        self._attr_media_title = None
        self._attr_media_artist = None
        self._attr_album_name = None
        self._attr_album_artist = None
        self._attr_media_position = None
        self._attr_media_position_updated_at = None
        self._attr_media_image_url = None
        self._attr_is_stream = False
        self._attr_extension = None

    def expand_url(self, source, url):
        parsed_url = urlparse.urlparse(url)
        if parsed_url.netloc == "":
            url = f"{self.local_url_base}{url}"
        query = dict(urlparse.parse_qsl(parsed_url.query))
        if query.get("t") is None:
            url_parts = list(urlparse.urlparse(url))
            query["t"] = int(time.time() * 1000)
            url_parts[4] = urlencode(query)
            url = urlparse.urlunparse(url_parts)

        return url

    def update(self):
        """Update media information"""
        self.clear()

        try:
            current_track = self.api.playback.get_current_track()
        except reConnectionError as error:
            _LOGGER.error(
                "Cannot get current track information"
            )
            _LOGGER.debug(str(error))

        try:
            current_stream_title = self.api.playback.get_stream_title()
        except reConnectionError as error:
            _LOGGER.error(
                "Cannot get current stream title"
            )
            _LOGGER.debug(str(error))

        try:
            current_media_position = self.api.playback.get_time_position()
        except reConnectionError as error:
            _LOGGER.error(
                "Cannot get current position"
            )
            _LOGGER.debug(str(error))

        if hasattr(current_track, "uri"):
            self._attr_track_uri = current_track.uri
            self._attr_extension = current_track.uri.partition(":")[0]
            self._attr_track_source = current_track.uri.partition(":")[0]

        try:
            if self.uri is not None:
                current_image = self.api.library.get_images([self.uri])
            else:
                current_image = None
        except reConnectionError as error:
            _LOGGER.error(
                "Cannot get image for media"
            )
            _LOGGER.debug(str(error))

        if hasattr(current_track, "track_no"):
            self._attr_track_number = int(current_track.track_no)

        if hasattr(current_track, "length"):
            self._attr_track_duration = int(current_track.length / 1000)

        if current_stream_title is not None:
            self._attr_media_title = current_stream_title
            self._attr_is_stream = True
            if hasattr(current_track, "name"):
                self._attr_media_artist = current_track.name
        else:
            if hasattr(current_track, "name"):
                self._attr_media_title = current_track.name
            if hasattr(current_track, "artists"):
                self._attr_media_artist = ", ".join([x.name for x in current_track.artists])

        if hasattr(current_track, "album") and hasattr(current_track.album, "name"):
            self._attr_album_name = current_track.album.name

        if hasattr(current_track, "artists"):
            self._attr_album_artist = ", ".join([x.name for x in current_track.artists])

        self._attr_media_position = int(current_media_position / 1000)
        self._attr_media_position_updated_at = dt_util.utcnow()

        if (
            current_image is not None
            and self.uri in current_image
            and len(current_image[self.uri]) > 0
            and hasattr(current_image[self.uri][0], "uri")
        ):
            self._attr_media_image_url = self.expand_url(self.source, current_image[self.uri][0].uri)


        if self._playlist_track_uris is not None and self.uri not in self._playlist_track_uris:
            self.clear_playlist()

    def clear_playlist(self):
        self._attr_playlist_name = None
        self._playlist_track_uris = None

    def set_local_url_base(self, value):
        self._attr_local_url_base = value

    def set_playlist(self, media_id):
        res = self.api.playlists.lookup(media_id)
        self._attr_playlist_name = res.name
        self._playlist_track_uris = [x.uri for x in res.tracks]

    @property
    def album_artist(self):
        """Return the Album artists"""
        return self._attr_album_artist

    @property
    def album_name(self):
        """Return the Album name"""
        return self._attr_album_name

    @property
    def artist(self):
        """Return the current track artist(s)"""
        return self._attr_media_artist

    @property
    def duration(self):
        """Return the duration of the current track"""
        return self._attr_track_duration

    @property
    def extension(self):
        """Return the extension (service) used"""
        return self._attr_extension

    @property
    def image_remotely_accessible(self):
        """Return whether image is remotely available"""
        return False

    @property
    def image_url(self):
        return self._attr_media_image_url

    @property
    def local_url_base(self):
        return self._attr_local_url_base

    @property
    def is_stream(self):
        return self._attr_is_stream

    # FIXME: need to figure out what to do with this...
    @property
    def playlist_name(self):
        """Return the current playlist"""
        if self._attr_playlist_name is not None:
            return self._attr_playlist_name
        else:
            return None

    @property
    def position(self):
        """Return the position of the playing track/stream"""
        return self._attr_media_position

    @property
    def position_updated_at(self):
        """Return the position of the playing track/stream"""
        return self._attr_media_position_updated_at

    @property
    def source(self):
        return self._attr_track_source

    @property
    def title(self):
        """Return the current track/stream title"""
        return self._attr_media_title

    @property
    def track_number(self):
        """Return the track number"""
        return self._attr_track_number

    @property
    def uri(self):
        """Return the URI of the current track"""
        return self._attr_track_uri

class MopidySpeaker:

    hass: HomeAssistant | None = None
    hostname: str | None = None
    port: int | None = None
    api: MopidyAPI | None = None
    snapshot: dict | None = None

    _attr_is_available: bool | None = None
    _attr_software_version: str | None = None
    _attr_supported_uri_schemes: list | None = None
    _attr_consume_mode: bool | None = None
    _attr_source_list: list | None = None
    _attr_volume_level: int | None = None
    _attr_is_volume_muted: bool | None = None
    _attr_state: MediaPlayerState | None = None
    _attr_repeat: RepeatMode | str | None = None
    _attr_shuffle: bool | None = None
    _attr_tracklist: list | None = None
    _attr_queue_position: int | None = None
    _attr_snapshot_at: datetime.datetime | None = None

    _attr_supported_features_base = (
        MediaPlayerEntityFeature.BROWSE_MEDIA
        | MediaPlayerEntityFeature.CLEAR_PLAYLIST
        | MediaPlayerEntityFeature.MEDIA_ENQUEUE
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.SEEK
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET

    )

    _attr_supported_features_media = (
        MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.REPEAT_SET
        | MediaPlayerEntityFeature.SHUFFLE_SET
    )

    def __init__(self,
        hass: HomeAssistant,
        hostname: str,
        port: int = None,
    ) -> None:
        self.hass = hass
        self.hostname = hostname
        if port is None:
            self.port = DEFAULT_PORT
        else:
            self.port = port

        self._attr_is_available = False
        self.media = MopidyMedia()
        self.media.set_local_url_base(f"http://{hostname}:{port}")
        self.library = MopidyLibrary()

        self.api = MopidyAPI(
            host=self.hostname,
            port=self.port,
            use_websocket=False,
            logger=logging.getLogger(__name__ + ".api"),
        )
        self.media.api = self.api
        self.library.api = self.api


    def clear(self):
        """Reset all Values"""
        self._attr_software_version = None
        self._attr_supported_uri_schemes = None
        self._attr_consume_mode = None
        self._attr_source_list = None
        self._attr_volume_level = None
        self._attr_is_volume_muted = None
        self._attr_state = None
        self._attr_repeat = None
        self._attr_shuffle = None
        self._attr_tracklist = None
        self._attr_queue_position = None
        self._attr_snapshot_at = None
        self._attr_is_available = False

    def update(self):
        self.clear()
        try:
            self.api.rpc_call("core.get_version")
            self._attr_is_available = True
        except reConnectionError as error:
            _LOGGER.error(
                "An error ocurred connecting to %s of port %s.",
                self.hostname,
                self.port
            )
            _LOGGER.debug(str(error))
            return

        self._attr_software_version = self.api.rpc_call("core.get_version")
        self._attr_supported_uri_schemes = self.api.rpc_call("core.get_uri_schemes")
        self._attr_consume_mode = self.api.tracklist.get_consume()
        self._attr_source_list = [x.name for x in self.library.playlists]
        self._attr_volume_level = self.api.mixer.get_volume()
        self._attr_is_volume_muted = self.api.mixer.get_mute()
        self._attr_shuffle = self.api.tracklist.get_random()
        self._attr_tracklist = self.api.tracklist.get_tracks()
        self._attr_queue_position = self.api.tracklist.index()

        state = self.api.playback.get_state()
        if state is None:
            self._attr_state = None
        elif state == "playing":
            self._attr_state = MediaPlayerState.PLAYING
        elif state == "paused":
            self._attr_state = MediaPlayerState.PAUSED
        elif state == "stopped":
            self._attr_state = MediaPlayerState.IDLE
        else:
            self._attr_state = None

        repeat = self.api.tracklist.get_repeat()
        single = self.api.tracklist.get_single()
        if repeat and single:
            self._attr_repeat = RepeatMode.ONE
        elif repeat and not single:
            self._attr_repeat = RepeatMode.ALL
        else:
            self._attr_repeat = RepeatMode.OFF

        self.media.update()

    def clear_queue(self):
        """Clear the playing queue"""
        self.api.tracklist.clear()

    def media_next_track(self):
        """Play next track"""
        self.api.playback.next()

    def media_pause(self):
        """Pause the current queue"""
        self.api.playback.pause()

    def media_play(self, index=None):
        """Play the current media"""
        if isinstance(index, int):
            self.api.playback.play(tlid=index)
        else:
            self.api.playback.play()

    def media_previous_track(self):
        """Play previous track"""
        self.api.playback.previous()

    def media_seek(self, value):
        self.api.playback.seek(value)

    def media_stop(self):
        """Play the current media"""
        self.api.playback.stop()

    def play_media(self, media_type, media_id, **kwargs):
        """Play the provided media"""

        enqueue = kwargs.get(ATTR_MEDIA_ENQUEUE, MediaPlayerEnqueue.REPLACE)
        _LOGGER.debug("media_type: %s", media_type)
        _LOGGER.debug("media_id: %s", media_id)

        media_uris = [media_id]
        self.media.clear_playlist()
        if media_type == MediaClass.PLAYLIST:
            media_uris = self.library.get_playlist_track_uris(media_id)
            self.media.set_playlist(media_id)

        if media_type == MediaClass.DIRECTORY:
            media_uris = [ x.uri for x in self.library.browse(media_id)]

        if enqueue == MediaPlayerEnqueue.ADD:
            self.queue_tracks(media_uris)
            self.media_play()

        elif enqueue == MediaPlayerEnqueue.NEXT:
            index = self.queue_position
            self.queue_tracks(media_uris, at_position=index+1)

        elif enqueue == MediaPlayerEnqueue.PLAY:
            index = self.queue_position
            self.queue_tracks(media_uris, at_position=index)
            self.media_play(index)

        elif enqueue == MediaPlayerEnqueue.REPLACE:
            self.clear_queue()
            self.queue_tracks(media_uris)
            self.media_play()

        else:
            _LOGGER.error("No media for %s (%s) could be found.", media_id, media_type)
            raise MissingMediaInformation

    def queue_tracks(self, uris, at_position=None):
        """Queue tracks"""
        if len(uris) > 0:
            self.api.tracklist.add(uris=uris, at_position=at_position)

    def restore_snapshot(self):
        """Restore a snapshot"""
        if self.snapshot is None:
            # TODO: Raise an error
            return
        self.media_stop()
        self.clear_queue()
        self.queue_tracks(self.snapshot.get("tracklist",[]))
        self.set_volume(self.snapshot.get("volume"))
        self.set_mute(self.snapshot.get("muted"))
        if self.snapshot.get("state", MediaPlayerState.IDLE) in [MediaPlayerState.PLAYING, MediaPlayerState.PAUSED]:
            current_tracks = self.api.tracklist.get_tl_tracks()
            self.api.playback.play(
                tlid=current_tracks[self.snapshot.get("tracklist_index")].tlid
            )

            count = 0
            while True:
                state = self.api.playback.get_state()
                if state in [MediaPlayerState.PLAYING, MediaPlayerState.PAUSED]:
                    break
                if count >= 120:
                    _LOGGER.error("media player is not playing after 60 seconds. Restoring the snapshot failed")
                    self.snapshot = None
                    return
                count = count +1
                time.sleep(.5)

            if self.snapshot.get("mediaposition",0) > 0:
                self.media_seek(self.snapshot["mediaposition"])

            if self.snapshot["state"] == MediaPlayerState.PAUSED:
                self.media_pause()

            self.snapshot = None
            self._attr_snapshot_at = None

    def select_source(self, value):
        """play the selected source"""
        for source in self.library.playlists:
            if value == source.name:
                self.play_media(MediaType.PLAYLIST, source.uri)
                return
        raise ValueError(f"Could not find source '{value}'")

    def set_consume_mode(self, value):
        if not isinstance(value, bool):
            return False

        if value != self._attr_consume_mode:
            self.api.tracklist.set_consume(value)

    def set_mute(self, value):
        """Mute/unmute the speaker"""
        self.api.mixer.set_mute(value)

    def set_repeat_mode(self, value):
        """Set repeat mode"""
        if value == RepeatMode.ALL:
            self.api.tracklist.set_repeat(True)
            self.api.tracklist.set_single(False)

        elif value == RepeatMode.ONE:
            self.api.tracklist.set_repeat(True)
            self.api.tracklist.set_single(True)

        else:
            self.api.tracklist.set_repeat(False)
            self.api.tracklist.set_single(False)

    def set_shuffle(self, value):
        self.api.tracklist.set_random(value)

    def set_volume(self, value):
        """Set the speaker volume"""
        if value is None:
            return
        if value >= 100:
            self.api.mixer.set_volume(100)
            self._attr_volume_level = 100
        elif value <= 0:
            self.api.mixer.set_volume(0)
            self._attr_volume_level = 0
        else:
            self.api.mixer.set_volume(value)
            self._attr_volume_level = value

    def take_snapshot(self):
        self.update()
        self._attr_snapshot_at = dt_util.utcnow()
        self.snapshot = {
            "mediaposition": self.media.position,
            "muted": self.is_muted,
            "repeat_mode": self.repeat,
            "shuffled": self.is_shuffled,
            "state": self.state,
            "tracklist": self.tracklist_uris,
            "tracklist_index": self.queue_position,
            "volume": self.volume_level,
        }

    def volume_down(self):
        """Turn down the volume"""
        self.set_volume(self._attr_volume_level - 1)

    def volume_up(self):
        """Turn up the volume"""
        self.set_volume(self.volume_level + 1)

    @property
    def consume_mode(self):
        """Return the consume mode of the the device"""
        return self._attr_consume_mode

    @property
    def features(self):
        if self.media.is_stream:
            return self._attr_supported_features_base
        else:
            return self._attr_supported_features_base | self._attr_supported_features_media

    @property
    def is_available(self):
        """Return whether the device is available"""
        return self._attr_is_available

    @property
    def is_muted(self):
        return self._attr_is_volume_muted

    @property
    def is_shuffled(self):
        return self._attr_shuffle

    @property
    def queue_position(self):
        """Return the index of the currently playing track in the tracklist"""
        return self._attr_queue_position

    @property
    def queue_size(self):
        """Return the size of the current playing queue"""
        if self._attr_tracklist is None:
            return None
        else:
            return len(self._attr_tracklist)

    @property
    def repeat(self):
        return self._attr_repeat

    @property
    def snapshot_taken_at(self):
        """Return the time the snapshot is taken at"""
        return self._attr_snapshot_at

    @property
    def software_version(self):
        """Return the software version of the Mopidy Device"""
        return self._attr_software_version

    @property
    def source_list(self):
        """Return the Source list of the Modpidy speaker"""
        return self._attr_source_list

    @property
    def state(self):
        return self._attr_state

    @property
    def supported_uri_schemes(self):
        """Return a list of supported URI schemes"""
        return self._attr_supported_uri_schemes

    @property
    def tracklist(self):
        """Return the current queue tracklist"""
        return self._attr_tracklist

    @property
    def tracklist_index(self):
        """Return the index of the currently playing track in the tracklist"""
        return self._attr_queue_position

    @property
    def tracklist_uris(self):
        """Return a list of track uris in the queue"""
        return [t.uri for t in self.tracklist]

    @property
    def volume_level(self):
        return self._attr_volume_level