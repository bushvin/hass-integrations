# Home Assitant integrations
Additional integrations for [Home Assistant](https://www.home-assistant.io/)

## Mopidy
This is a platform integration for [Mopidy Music Servers](https://mopidy.com/)

### Installation
Please look at the [Mopidy installation & configuration instructions](https://docs.mopidy.com/en/latest/installation/) to set up a Mopidy Server.

1. Install HACS
2. Go to any of the sections (integrations, frontend, automation).
3. Click on the 3 dots in the top right corner.
4. Select "Custom repositories"
5. Add the URL to the repository.
6. Select the correct category.
7. Click the "ADD" button.
8. Go to Home Assistaat settings -> Integrations and add Mopidy
9. Restart HA

### Setup
#### zeroconf
Your Mopidy Servers can be detected and addedto Home Assitant through zeroconf.

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
#### Service media_player.play_media
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

#### Service mopidy.snapshot
Take a snapshot of what is currently playing on one or more Mopidy Servers. This service, and the following one, are useful if you want to play a doorbell or notification sound and resume playback afterwards.

**Warning:** *This service is controlled by the platform, this is not a built-in function of Mopidy Server! Restarting Home Assistant will cause the snapshot to lost.*

|Service data attribute|Optional|Description|
|-|-|-|
|`entity_id`|no|String or list of `entiti_id`s ito take a snapshot of.|


### Notes
Due to the nature of the way Mopidy provides thumbnails of the media,
proxying them through Home Assistant is very resource intensive, 
causing delays. Therefore, I have decided to not proxy the art when
using the Media Library for the time being.

### Tests
Mopidy v3.1.1

Backends:
- mopidy-beets v4.0.1
- mopidy-dleyna 2.0.1
- mopidy-internetarchive v3.0.0
- mopidy-local v3.2.0
- mopidy-podcast v3.0.0
- mopidy-somafm v2.0.0
- mopidy-soundcloud v3.0.1
- mopidy-spotify v4.1.0
- mopidy-tunein v1.0.2
- mopidy-YouTube v3.2

