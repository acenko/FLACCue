import os
import traceback

import mutagen.flac

import AudioFiles
import Media

debug = False
logfile = []
if(debug):
   # During debugging, we just append to a fixed file path. Change this to something appropriate for your
   # system if needed.
   logfile.append(open('/volume1/Plex/Library/Application Support/Plex Media Server/Logs/custom_scanner.log', 'a'))

def log(message):
   if(debug):
      logfile[0].write('{0}\n'.format(message))

def Scan(path, files, mediaList, subdirs, language=None, root=None):
   """Handle FLAC with Cue.
   Find any Cue files in the input list.
   """
   cues = []
   for f in files:
      if(os.path.splitext(f)[1] == '.cue'):
         cues.append(f)
   for cue in cues:
      log(cue)
      try:
         # Get the Cue sheet info.
         info = read_cue(cue)
         log(info)
         # Get all files mentioned in the Cue sheet.
         cuefiles = info['Files']
         # Get the directory the files should be in. This should be
         # the same as the Cue sheet directory.
         folder = os.path.dirname(cue)
         for file in cuefiles:
            # Get the full FLAC file path.
            full_file = os.path.join(folder, file)

            # My FLAC files include "Disc 1", "Disc 2", and similar as the
            # final part of the title for multi-disk sets. Something like:
            # "Artist - Album Title Disc 3.flac"
            # The scanner is designed to pull disc information from this
            # and to group albums together.

            # Get the name of the FLAC file without the extension.
            # Split it for white space.
            flac_details = os.path.splitext(file)[-2].split()
            # Check for disc numbering.
            if(flac_details[-2] == 'Disc'):
               disc = int(flac_details[-1])
            else:
               disc = 1

            try:
               # Add the full FLAC file.
               # Number it as track -1.
               track = -1
               # Get the file info for the full FLAC file.
               flac_info = mutagen.flac.FLAC(full_file)
               # Add the additional disc number information.
               flac_info['discnumber'] = ['{0:0d}'.format(disc)]
               # Make this track -1.
               flac_info['tracknumber'] = ['{0:02d}'.format(track)]
               # Call this "Album Name - Full Album" in the track listing
               flac_info['title'] = ['{0} - Full album'.format(flac_info['album'][0])]
               # Ensure the info is added cleanly.
               artist = AudioFiles.cleanPass(flac_info['artist'][0])
               album = AudioFiles.cleanPass(flac_info['album'][0])
               title = AudioFiles.cleanPass(flac_info['title'][0])
               album_artist = AudioFiles.cleanPass(flac_info['albumartist'][0])
               # Create the track object.
               track_object = Media.Track(artist, album, title, track,
                                          disc=disc, album_artist=album_artist,
                                          guid=None, album_guid=None)
               # Use the FLAC file for playback.
               track_object.parts.append(full_file)
               log(track_object)
               log('')
               # Add the track object to the output list.
               mediaList.append(track_object)
               
               # Split into tracks.
               track_info = cuefiles[file]['Tracks']
               start_time = '00:00:00'
               end_time = '00:00:00'
               # Handle each track.
               for track in track_info:
                  # Get a copy of the shared info.
                  flac_info = mutagen.flac.FLAC(full_file)
                  # Add the disc number.
                  flac_info['discnumber'] = ['{0:0d}'.format(disc)]
                  # Add the track number.
                  flac_info['tracknumber'] = ['{0:02d}'.format(track)]
                  # Add the track title.
                  flac_info['title'] = [track_info[track]['TITLE']]
                  try:
                     # Get the start time of the track.
                     start_time = track_info[track]['INDEX'][1]
                  except KeyError:
                     # If none is listed, use the previous end time.
                     start_time = end_time
                  try:
                     # Get the start time of the following track.
                     # Use this as the end time for the current track.
                     end_time = track_info[track+1]['INDEX'][1]
                  except (IndexError, KeyError):
                     # For the last track, we just take the end time of the
                     # FLAC file as the end of the song.
                     file_end = flac_info.info.length
                     minutes = int(file_end / 60)
                     seconds = int(file_end % 60)
                     # 75 frames per second.
                     frames = int(round(75 * (file_end % 1)))
                     end_time = '{0:02d}:{1:02d}:{2:02d}'.format(minutes, seconds, frames)
                  # Ensure the info is added cleanly.
                  artist = AudioFiles.cleanPass(flac_info['artist'][0])
                  album = AudioFiles.cleanPass(flac_info['album'][0])
                  title = AudioFiles.cleanPass(flac_info['title'][0])
                  album_artist = AudioFiles.cleanPass(flac_info['albumartist'][0])
                  # Create the track object.
                  track_object = Media.Track(artist, album, title, track,
                                             disc=disc, album_artist=album_artist,
                                             guid=None, album_guid=None)
                  # Use a file format for compatibility with the FLACCue
                  # FUSE (Filesystem in Userspace) code.
                  # This will be something like:
                  # /flaccue/Music/Artist/Album/Artist - Album Disc 1.flac.10:25:17.12:55:20
                  track_object.parts.append('/flaccue'+full_file+'.{0}.{1}'.format(start_time, end_time))
                  log(track_object)
                  log('')
                  # Add the track to the returned object list.
                  mediaList.append(track_object)
               # Remove the FLAC file from the list to parse.
               files.remove(full_file)
            except:
               log(traceback.format_exc())
      except:
         log(traceback.format_exc())
      finally:
         files.remove(cue)

   # Scan for other audio files, including those that failed to process correctly.
   AudioFiles.Scan(path, files, mediaList, subdirs, root=root)

   # Read tags, etc. and build up the mediaList
   AudioFiles.Process(path, files, mediaList, subdirs, language=language, root=root)

def read_cue(file):
   """Parse the Cue sheet to get the desired info.
   """
   # Read the full Cue file.
   with open(file, 'r') as f:
      lines = f.readlines()
   cue = {}
   cue['Files'] = {}
   # Line index. We don't use a for loop as we will
   # read multiple lines for information.
   i = 0
   lenlines = len(lines)
   try:
      while(True):
         # We have a FILE specification in the Cue sheet.
         if(lines[i].startswith('FILE')):
            # Get the filename.
            filename = AudioFiles.cleanPass(lines[i].split('"')[1])
            # Now we will parse the tracks from the file.
            # Use a local variable name for clarity.
            file_details = {}
            # But store that variable in the cue sheet parse dictionary.
            cue['Files'][filename] = file_details
            # Create the Track entry to store tracks from the file.
            file_details['Tracks'] = {}
            # Start at the next line.
            i += 1
            # Use the Cue sheet indentation for sectioning. 2 spaces for
            # TRACK entries in the FILE entry.
            while(lines[i].startswith(' '*2)):
               # Get rid of extra white space.
               line = lines[i].strip()
               # Handle TRACK entries.
               if(line.startswith('TRACK')):
                  # Get the track number.
                  track = int(line.split()[1])
                  # Use a local variable name for clarity.
                  track_details = {}
                  # But store that variable in the cue sheet parse dictionary.
                  file_details['Tracks'][track] = track_details
                  # Create the INDEX dictionary to store track indices.
                  track_details['INDEX'] = {}
                  # Start at the next line.
                  i += 1
                  # Use the Cue sheet indentation for sectioning. 4 spaces
                  # for INDEX entries in the TRACK entry.
                  while(lines[i].startswith(' '*4)):
                     # Get rid of extra white space.
                     line = lines[i].strip()
                     # Find the index entries.
                     if(line.startswith('INDEX')):
                        # Remove the INDEX text and extra white space.
                        line = line[5:].strip()
                        # Get the INDEX number and the rest of the line.
                        # The rest of the line should be the time information.
                        key, value = line.split(None, 1)
                        # Store the time information for this index.
                        track_details['INDEX'][int(key)] = value.replace('"', '')
                        i += 1
                     else:
                        # Store all the other entries as text. Use the first
                        # word as the access key.
                        key, value = line.split(None, 1)
                        # Also remove quotes from track names and similar.
                        track_details[key] = value.replace('"', '')
                        i += 1
               else:
                  # Store all the other entries as text. Use the first
                  # word as the access key.
                  key, value = lines[i].split(None, 1)
                  # Also remove quotes from track names and similar.
                  file_details[key] = value.replace('"', '')
                  i += 1
         else:
            # Store all the other entries as text. Use the first
            # word as the access key.
            key, value = lines[i].split(None, 1)
            # Also remove quotes from track names and similar.
            cue[key] = value.replace('"', '')
            i += 1
   except IndexError:
      # We're done.
      pass
   return cue
