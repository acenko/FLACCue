# FLACCue
FLAC with cuesheet support for Plex.

The Plex Media Server directory includes the Scanner for parsing cue sheets
for the FLAC files. It will create Plex albums for the cue sheets with the
full album available as disc 9999, track [Disc #] and also the split up tracks.
The tracks give Plex filenames with
"/flaccue/{file base}.flaccuesplit.{start_time}.{end_time}.{ext}".
This causes each track to have a unique filename (seemingly necessary) and
also provides the track timing information. The "/flaccue" portion indicates
to the file system to access the FUSE filesystem for extracting the tracks.

My FLAC files also include "Disc 1", "Disc 2", and similar as the final
part of the title for multi-disk sets. Something like:
"Artist - Album Title Disc 3.flac"
The scanner is also designed to pull disc information from this and to group
albums together.

The file "flaccue.py" is a FUSE filesystem that allows accessing tracks include
the FLAC files. This is a python script that requires the mirrored directory ('/')
and the mount location ('/flaccue') as parameters. You can access any portion
of a FLAC file through this filesystem--I've also used it to extract specific
song subportions out of the FLAC file for burning onto CDs. You just provide
the appropriate start and end times in the filename. Note that FLAC times are
specified in cue sheets as MM:SS:FF where MM is minutes, SS is seconds, and
FF is frame information (1/75th of a second) and this is the format FLACCue
understands.

You do not want to run this script as root as this will give anyone read
access to any file. Use something like this instead:
sudo --user=plex nohup flaccue.py / /flaccue/ &


As my Plex server runs on a Synology webserver, I've also created a Synology
package to run the FLACCue script automatically. The source for creating this
package can be found in the synology_package directory. You can compile this
with pkgscripts from Synology:
https://github.com/SynologyOpenSource/pkgscripts-ng

After creating the toolkit, you put the FLACCue folder in the "toolkit/source"
directory and run this command from the "toolkit/" directory:
sudo pkgscripts/PkgCreate.py -S -c FLACCue

Note that the python script is called "FLACCue" in this package instead of
flaccue.py. The files are the same other than the name. I also installed
FFMPEG and Python3 through the Package Center--they are needed for the code
to run.

I've also included an unsigned spk file you can install directly at your own
risk in the synology_package directory.
