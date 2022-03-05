# Home Assitant integrations
Additional integrations for [Home Assistant](https://www.home-assistant.io/)

## Mopidy
This is a platform integration for [Mopidy Music Servers](https://mopidy.com/)

### Installation
Please look at the [Mopidy installation & configuration instructions](https://docs.mopidy.com/en/latest/installation/) to set up a Mopidy Server.

#### HACS
1. Install [HACS](https://hacs.xyz)
1. Go to any of the sections (integrations, frontend, automation).
1. Click on the 3 dots in the top right corner.
1. Select "Custom repositories"
1. Add the URL to the repository.
1. Select the correct category.
1. Click the "ADD" button.
1. Go to Home Assistaat settings -> Integrations and add Mopidy
1. Restart HA

#### Manual
1. Clone this repository
2. Copy `custom_components/mopidy` to your Home Assistant insance on `<config dir>/custom_components/`

### Setup
#### zeroconf
Your Mopidy Servers can be detected and addedi to Home Assitant through zeroconf.

#### GUI
1. Go to the *Integrations* page and click **+ ADD INTEGRATION**
1. Select *Mopidy* in the list of integrations
1. Fill out the requested information. Make sure to enter your correct FQDN or IP address. Using `localhost`, `127.0.0.1`, `::1` or any other loopback address will disable Mopidy-Local artwork.
1. Click Submit.

Repeat the above steps to add more Mopidy Server instances.

#### Manual Configuration
1. add a media player to your home assistant configuration (`<config dir>/configuration.yaml`):

```yaml
media_player:
- name: <mopidy identifier>
  host: <FQDN or IP address>
  port: <port if different from 6680>
  platform: mopidy
```
2. Restart your Home assistant to make changes take effect.

### Configuration

```yaml
- name: <mopidy name>      # The name of your Mopidy server.
  host: <fqdn/ip address>  # The FQDN or IP address of your Mopidy Server, do not use ::1, localhost or 127.0.0.1
  port: <port number>      # The port number of the Mopidy Server, default: 6680
  platform: mopidy         # specify mopidy platform
```

### Services
#### Service media\_player.play\_media
The `media_content_id` needs to be formatted according to the Mopidy URI scheme. These can be easily found using the *Developer tools*.

When using the `play_media` service, the Mopidy Media Player platform will attempt to discover your URL when not properly formatted.
Currently supported for:
- Youtube

#### Service mopidy.restore
Restore a previously taken snapshot of one or more Mopidy Servers

The playing queue is snapshotted

|Service data attribute|Optional|Description|
|-|-|-|
|`entity_id`|no|String or list of `entiti_id`s that should have their snapshot restored.|

#### Service mopidy.search
Search media based on keywords and add them to the queue. This service does not replace the queue, nor does it start playing the queue. This can be achieved through the use of [media\_player.clear\_playlist](https://www.home-assistant.io/integrations/media_player/) and [media\_player.media\_play](https://www.home-assistant.io/integrations/media_player/)

**Note:** One of the keyword fields **must** be used: `keyword`, `keyword_album`, `keyword_artist`, `keyword_genre` or `keyword_track_name`

|Service data attribute|Optional|Description|Example|
|-|-|-|-|
|`entity_id`|no|String or list of `entiti_id`s ito take a snapshot of.| |
|`exact`|yes|String. Should the search be an exact match|false|
|`keyword`|yes|String. The keywords to search for. Will search all track fields.|Everlong|
|`keyword_album`|yes|String. The keywords to search for in album titles.|From Mars to Sirius|
|`keyword_artist`|yes|String. The keywords to search for in artists.|Queens of the Stoneage|
|`keyword_genre`|yes|String. The keywords to search for in genres.|rock|
|`keyword_track_name`|yes|String. The keywords to search for in track names.|Lazarus|
|`source`|yes|String. URI sources to search. `local`, `spotify` and `tunein` are the only supported options. Make sure to have these extensions enabled on your Mopidy Server! Separate multiple sources with a comma (,).|local,spotify|

#### Service mopidy.snapshot
Take a snapshot of what is currently playing on one or more Mopidy Servers. This service, and the following one, are useful if you want to play a doorbell or notification sound and resume playback afterwards.

**Warning:** *This service is controlled by the platform, this is not a built-in function of Mopidy Server! Restarting Home Assistant will cause the snapshot to be lost.*

|Service data attribute|Optional|Description|
|-|-|-|
|`entity_id`|no|String or list of `entiti_id`s ito take a snapshot of.|


### Notes
Due to the nature of the way Mopidy provides thumbnails of the media,
proxying them through Home Assistant is very resource intensive, 
causing delays. Therefore, I have decided to not proxy the art when
using the Media Library for the time being.

### Tests
Mopidy v3.2.0

Backends:
- mopidy-beets v4.0.1
- mopidy-dleyna 2.0.1
- mopidy-internetarchive v3.0.0
- mopidy-local v3.2.1
- mopidy-podcast v3.0.0
- mopidy-somafm v2.0.2
- mopidy-soundcloud v3.0.1
- mopidy-spotify v4.1.1
- mopidy-tunein v1.1.0
- mopidy-YouTube v3.2

