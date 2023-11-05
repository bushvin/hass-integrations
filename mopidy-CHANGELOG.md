# Change log
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.3] - 2023-11-05

### Fixed

- fix `media_player.play_media` service `enqueue.play` behaviour

## [2.0.2] - 2023-11-02

### Fixed

- wrong varname for youtube (#40)

## [2.0.1] - 2023-10-31

### Changed

- Better handling of youtube URLs based on available extensions
- Complete the media URL with hostname and timestamps if not available

## [2.0.0] - 2023-10-31

This version incorporates a refactor of the integration to include numerous new
Home Assistant `media_player` features. I did not keep track of all features updated, but these incorporate the major ones

### Added

- Support for `media_player.play_media` `enqueue` feature
- `mopid.set_consume_mode` service
- `consume_mode` entity attribute for the current consume_mode
- `mopidy_extension` entity attribute for currently used extension
- `queue_position` entity attribute for the index of the currently playing track in the queue
- `queu_size` entity attribute for the number of tracks in the currently playing queue
- `snapshot_taken_at` entity attribute to show when the snapshot was taken (if any)

### Fixed

- Wrong volume level on snapshot restore

### Removed

- Support for ON/OFF, as these refer to a physical ON/OFF switch.

## [1.4.8] - 2023-05-31

### Changed

- Modified the way playlists are handled in the play queue

### Fixed

- FIX Issue #26: Tidal playlists not expanding correctly

## [1.4.7] - 2022-09-24

### Fixed

- BUGFIX: playing mopidy-local "directory" resources (eg `artists/albums`) failed as the resource is not considered
  a media source according to URI\_SCHEME\_REGEX
- typo in the README.md

### Added

- support for mopidyapi>=1.0.0, no need to stay in the stoneage

## [1.4.6] - 2022-03-06
### Fixed
- playing from local media (thanks, [koying](https://github.com/koying))

## [1.4.5] - 2022-03-05
### Added
- Support for media browsing and playing from other components in HA (thanks, [koying](https://github.com/koying))

## [1.4.4] - 2022-02-19
### Fixed
- change of code for 2022.6 warning introduced issue where an int was added to a string.

## [1.4.3] - 2022-01-07
### Fixed
- git version tag added before last PR

## [1.4.2] - 2022-01-03
- mopidy play instruction is slow on streming media. now waiting for status to change into `playing` asynchronously
- update code to comply with 2022.6 deprecation (thanks, [VDRainer](https://github.com/VDRainer))

## [1.4.1] - 2021-05-23
### Changed
- bugfix: snapshot and restore player state (thanks [AdmiralStipe](https://community.home-assistant.io/u/AdmiralStipe))
- better messages when device detected through zeroconf is not a mopidy server
- formatting (pylint, pep8, pydocstyle)
- fix zeroconf issues on docker (thanks, [@guix77](https://github.com/guix77))
- set name to zeroconf name and port

## [1.4.0] - 2021-04-05
### Changed
- fixed issue with logging on detected non-mopidy zeroconf http devices
- added service `search`
- change service targetting
- sort the sourcelist
- modifications to pass tests to add to core

## [1.3.2] - 2021-03-14
### Changed
- refactored media library routines
- provide home assistant logger to MopidyAPI

## [1.3.1] - 2021-03-13
### Changed
- fixed issue with snapshot/restore track index

## [1.3.0] - 2021-03-12
### Added
- snapshot service
- restore service
- dutch translation
- french translation

### Changed
- fixed typo in english translation

## [1.2.0] - 2021-03-08
### Added
- Support for zeroconf discovery

## [1.1.4] - 2021-03-06
### Changed
- Handle connection errors in a better way

## [1.1.3] - 2021-03-06
### Changed
- uids based on hostname and port number instead of hostname only, thenks @Burningstone91

