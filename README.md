# Home Assitant integrations
Additional intagrations for [Home Assistant](https://www.home-assistant.io/)

## Mopidy
This is a platform integration for [Mopidy Music Servers](https://mopidy.com/)

### Installation
Please look at the [Mopidy installation & configuration instructions](https://docs.mopidy.com/en/latest/installation/) to set up a Mopidy Server.

1. Clone this repository
2. Copy the `mopidy` directory to `<config dir>/custom_components/`

### Setup
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
  host: <fqdn/ip address>  # The FQDN or IP address of your Mopidy Server
  port: <port number>      # The port number of the Mopidy Server, default: 6680
  platform: mopidy         # specify mopidy platform
```

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

