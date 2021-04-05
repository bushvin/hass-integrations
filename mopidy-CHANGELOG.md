# Change log
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Changed
- better messages when device detected through zeroconf is not a mopidy server
- formatting (pylint, pep8, pydocstyle)

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

