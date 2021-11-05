import os
import traceback

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


def FLACCueParse(path, files, mediaList, subdirs, language=None, root=None):
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
         # Get the album information.
         album = info['TITLE']
         album_artist = AudioFiles.cleanPass(info['PERFORMER'])
         if(album_artist == ''):
            # No listed album artist. Use the artist from the first
            # track of the first file.
            try:
               first_file = list(cuefiles.keys())[0]
               album_artist = cuefiles[first_file]['Tracks'][1]['PERFORMER']
            except KeyError:
               album_artist = 'Unknown'
         # Get the directory the files should be in. This should be
         # the same as the Cue sheet directory.
         folder = os.path.dirname(cue)
         for file in cuefiles:
            # Get the full file path.
            full_file = os.path.join(folder, file)
            if(not os.path.exists(full_file)):
               continue

            # My cue files include "Disc 1", "Disc 2", and similar as the
            # final part of the title for multi-disk sets. Something like:
            # "Artist - Album Title Disc 3.cue"
            # The scanner is designed to pull disc information from this
            # and to group albums together.

            # Get the name of the cue file without the extension.
            # Split it for white space.
            try:
               file_details = os.path.splitext(file)[-2].split()
               # Check for disc numbering.
               if(file_details[-2] == 'Disc'):
                  disc = int(file_details[-1])
               else:
                  disc = 1
            except IndexError:
               disc = 1

            try:
               # Add the full file.
               # Number it as track -1.
               track = -1
               # Call this "Album Name - Disc #" in the track listing
               # Ensure the info is added cleanly.
               title = '{0} - Disc {1}'.format(album, disc)
               title = AudioFiles.cleanPass(title)
               artist = AudioFiles.cleanPass(album_artist)
               # Create the track object.
               # Use disc 9999 to group all the full discs together. Use
               # the disc number as the track number.
               track_object = Media.Track(artist, album, title, disc,
                                          disc=9999, album_artist=album_artist,
                                          guid=None, album_guid=None)
               # Use the file for playback.
               track_object.parts.append(full_file)
               log(track_object)
               # Add the track object to the output list.
               mediaList.append(track_object)

               # Split into tracks.
               track_info = cuefiles[file]['Tracks']
               start_time = '00:00:00'
               end_time = '00:00:00'
               # Handle each track.
               for track in track_info:
                  title = AudioFiles.cleanPass(track_info[track]['TITLE'])
                  try:
                     artist = AudioFiles.cleanPass(track_info[track]['PERFORMER'])
                  except KeyError:
                     # No track artist specified. Use the album artist.
                     artist = album_artist
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
                     # For the last track, we specify -1 to indicate the end of file.
                     end_time = '-1'
                  # Create the track object.
                  track_object = Media.Track(artist, album, title, track,
                                             disc=disc, album_artist=album_artist,
                                             guid=None, album_guid=None)
                  # Use a file format for compatibility with the FLACCue
                  # FUSE (Filesystem in Userspace) code.
                  # This will be something like:
                  # /flaccue/Music/Artist/Album/Artist - Album Disc 1.flaccuesplit.10:25:17.12:55:20.flac
                  parsed_filename = '/flaccue'+full_file+'.flaccuesplit.{}.{}.wav'.format(start_time, end_time)
                  track_object.parts.append(parsed_filename)
                  log(track_object)
                  # Add the track to the returned object list.
                  mediaList.append(track_object)
               log('')
               # Remove the FLAC file from the list to parse.
               files.remove(full_file)
            except:
               log(traceback.format_exc())
      except:
         log(traceback.format_exc())
      finally:
         files.remove(cue)


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
                        track_details['INDEX'][int(key)] = value.strip().replace('"', '')
                        i += 1
                     else:
                        # Store all the other entries as text. Use the first
                        # word as the access key.
                        key, value = line.split(None, 1)
                        # Also remove quotes from track names and similar.
                        track_details[key] = value.strip().replace('"', '')
                        i += 1
               else:
                  # Store all the other entries as text. Use the first
                  # word as the access key.
                  key, value = lines[i].split(None, 1)
                  # Also remove quotes from track names and similar.
                  file_details[key] = value.strip().replace('"', '')
                  i += 1
         else:
            # Store all the other entries as text. Use the first
            # word as the access key.
            key, value = lines[i].split(None, 1)
            # Also remove quotes from track names and similar.
            cue[key] = value.strip().replace('"', '')
            i += 1
   except IndexError:
      # We're done.
      pass
   return cue
