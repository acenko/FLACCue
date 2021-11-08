# FLACCue
FLAC cuesheet support in a FUSE filesystem. Designed to integrate with Plex.

When running, this filesystem will automatically expand .cue files into
separate tracks. When accessing the tracks, it will use ffmpeg to extract
the appropriate segment of the files for playback. This filesystem also
allows accessing portions of any music file using a specific filename
structure:
"/flaccue/{file name}.flaccuesplit.{start_time}.{end_time}.{ext}".
The "/flaccue" portion is the path where the FUSE filesystem is mounted.
{filename} is the full path to the base file on the original fileystem,
including the file extension. {ext} should match whatever extension
option is chosen for the FUSE filesystem (default wav). The default
settings also cache the parsed cue files, using up a noticeable amount
of memory for increased speed (although, with my library, still less
memory than the extracted tracks use while actively listening to music).
Actively extracted tracks will persist in memory from when the track is
opened until one minute past the last file handle accessing the track
is closed--while generally this will only involve a couple of tracks in
memory at any given time, this can balloon somewhat during scanning and
similar.

This structure will directly work with the native Plex scanners, allowing
use of the full Plex Music Scanner unlike previous versions of this
package. The filesystem overhead does matter (e.g., encoding the tracks
into FLAC files causes failures in Plex on my system when track lengths
exceeded ~15 minutes, causing hangups in playback) but the default settings
work reliably on my Synology NAS (with output files in wav format vs flac
being the biggest and most necessary speed increase I found). To use in
this method, you would simply tell the Plex Scanner to scan the
/flaccue/{path_to_music} folder.

The Plex Media Server directory includes an updated Scanner for parsing cue
sheets for the FLAC files, bypassing the direct FUSE cue parsing. It will
create Plex albums for the cue sheets with the album available as disc 9999,
track [Disc #] (comment out line 90 in flaccuelib.py to disable the full
album) and also the split up tracks. The tracks give Plex filenames with
"/flaccue/{file name}.flaccuesplit.{start_time}.{end_time}.{ext}".
This causes each track to have a unique filename (seemingly necessary) and
also provides the track timing information. This bypasses the need for the
FUSE filesystem to parse cue files to access specific tracks, somewhat
increasing access speed at the cost of needing a custom Scanner. That said,
in getting the FUSE filesystem to work directly I found many places to
improve reliability. Sadly, you will need to rescan any libraries using
this scanner as I needed to slightly change the filename format for
accessing tracks through the flaccue filesystem.

My FLAC files also include "Disc 1", "Disc 2", and similar as the final
part of the title for multi-disk sets. Something like:
"Artist - Album Title Disc 3.flac"
The scanner is designed to pull disc information from this and to group
albums together, while the direct FUSE filesystem will number tracks
including the disc number (e.g., 203 for track 3 on disc 2).

The file "flaccue.py" is the FUSE filesystem. This is a python script that
requires the mirrored directory ('/') and the mount location ('/flaccue')
as parameters. You can access any portion of a FLAC file through this
filesystem--I've also used it to extract specific song subportions out of
the FLAC file for burning onto CDs. You just provide the appropriate start
and end times in the filename. Note that FLAC times are specified in cue
sheets as MM:SS:FF where MM is minutes, SS is seconds, and FF is frame
information (1/75th of a second) and this is the format FLACCue understands.

You do not want to run this script as root as this will give anyone read
access to any file. Use something like this instead:
sudo --user=flaccue nohup flaccue.py / /flaccue/ &


As my Plex server runs on a Synology webserver, I've also created a Synology
package to run the FLACCue script automatically. The source for creating this
package can be found in the synology_package directory. You can compile this
with pkgscripts from Synology:
https://github.com/SynologyOpenSource/pkgscripts-ng

After creating the toolkit, you put the FLACCue folder in the "toolkit/source"
directory and run this command from the "toolkit/" directory:
sudo pkgscripts/PkgCreate.py -v 7.0 -c FLACCue

Note that you may need to set permissions on INFO.sh to be executable.
Also note that the python script is called "FLACCue" in this package instead
of flaccue.py. The files are the same other than the name.

I've included an unsigned spk file you can install directly at your own
risk in the synology_package directory. FFMPEG will need to be installed
(and the spk should warn you of this if it's not already there).

Synology no longer allows root access for a package that isn't signed by
Synology. As such, for installing the spk, you'll also need to log in as
root and run:
```
sudo -i

curl -k https://bootstrap.pypa.io/get-pip.py | python3
pip install ffmpeg-python mutagen numpy

mkdir /flaccue
chown flaccue:flaccue /flaccue
```
You'll need to do this after the package is installed and before it will
successfully load. You'll also need to provide permissions for the flaccue
user to access any media files you want it to be able to. Read-only access
is likely best.