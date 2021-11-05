#!/bin/bash

source /pkgscripts/include/pkg_util.sh

package="FLACCue"
version="3.0.0000"
os_min_ver="7.0-40000"
displayname="FLACCue"
maintainer="Andrew Cenko"
maintainer_url="https://github.com/acenko/FLACCue"
arch="noarch"
description="Run a Fuse server to trim FLAC files according to Cue."
install_dep_packages="ffmpeg:python3"
[ "$(caller)" != "0 NULL" ] && return 0
pkg_dump_info
