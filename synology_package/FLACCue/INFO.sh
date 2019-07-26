#!/bin/bash

source /pkgscripts/include/pkg_util.sh

package="FLACCue"
version="2.0.0002"
displayname="FLACCue"
maintainer="Andrew Cenko"
arch="$(pkg_get_unified_platform)"
description="Run a Fuse server to trim FLAC files according to Cue sheets for Plex."
[ "$(caller)" != "0 NULL" ] && return 0
pkg_dump_info
