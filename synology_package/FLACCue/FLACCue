#!/usr/bin/env python3

# Note that you do not want to run this as root as this will
# give anyone read access to any file by just prepending /flaccue/.

from __future__ import print_function, absolute_import, division

import logging
import os

import ffmpeg
import mutagen
import numpy
import time
import threading

from errno import EACCES
from os.path import realpath

import sys
sys.path.insert(0, '.')

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn


class FLACCue(LoggingMixIn, Operations):
   def __init__(self, root):
     self.root = realpath(root)
     self.rwlock = threading.RLock()
     self._open_subtracks = {}

   def __call__(self, op, path, *args):
      return super(FLACCue, self).__call__(op, self.root + path, *args)

   def clean_path(self, path):
      # Get a file path for the FLAC file from a FLACCue path.
      # Note that files accessed through FLACCue will
      # still read normally--we just need to trim off the song
      # times.
      if('.flaccuesplit.' in path):
         splits = path.split('.flaccuesplit.')
         times, extension = os.path.splitext(splits[1])
         try:
            # The extension should not parse as an int nor split into ints
            # separated by :. If it does, we have no extension.
            int(extension.split(':')[0])
            extension = ''
         except ValueError:
            pass
         path = splits[0] + extension
      return path

   def getattr(self, path, fh=None):
      # If it's one of the FLACCue paths, we need to adjust the file size to be
      # appropriate for the shortened data.
      if('.flaccuesplit.' in path):
         try:
            splits = path.split('.flaccuesplit.')
            times, extension = os.path.splitext(splits[1])
            try:
               # The extension should not parse as an int nor split into ints
               # separated by :. If it does, we have no extension.
               int(extension.split(':')[0])
               extension = ''
            except ValueError:
               pass
            path = splits[0] + extension
            # Get the info for the base file.
            st = os.lstat(path)
            toreturn = dict((key, getattr(st, key)) for key in (
                            'st_atime', 'st_ctime', 'st_gid', 'st_mode', 'st_mtime',
                            'st_nlink', 'st_size', 'st_uid'))
            # Estimate the file size.
            f = mutagen.File(path)
            start, end = times.split('.')
            # Minutes:Seconds:Frames
            # 75 frames per second.
            start_split = [int(x) for x in start.split(':')]
            if(len(start_split) != 3):
               start_time = 0
            else:
               start_time = start_split[0]*60 + start_split[1] + start_split[2]/75
            end_split = [int(x) for x in end.split(':')]
            if(len(end_split) != 3):
               end_time = f.info.length
            else:
               end_time = end_split[0]*60 + end_split[1] + end_split[2]/75
            toreturn['st_size'] = int((end_time - start_time) *
                                      f.info.channels *
                                      (f.info.bits_per_sample/8) *
                                      f.info.sample_rate)
            return toreturn
         except:
            import traceback
            traceback.print_exc()
      # Otherwise, just get the normal info.
      path = self.clean_path(path)
      st = os.lstat(path)
      return dict((key, getattr(st, key)) for key in (
         'st_atime', 'st_ctime', 'st_gid', 'st_mode', 'st_mtime',
         'st_nlink', 'st_size', 'st_uid'))

   getxattr = None

   listxattr = None

   def open(self, path, flags, *args, **pargs):
      # We don't want FLACCue messing with actual data.
      # Only allow Read-Only access.
      if((flags | os.O_RDONLY) == 0):
         raise ValueError('Can only open files read-only.')
      raw_path = path
      # Handle the FLACCue files.
      if('.flaccuesplit.' in path):
         splits = path.split('.flaccuesplit.')
         # Get a path to the actual file name.
         # Note that files accessed through FLACCue will
         # still read normally--we just need to trim off the song
         # times and fix the file extension.
         times, extension = os.path.splitext(splits[1])
         try:
            # The extension should not parse as an int nor split into ints
            # separated by :. If it does, we have no extension.
            int(extension.split(':')[0])
            extension = ''
         except ValueError:
            pass
         path = splits[0] + extension
         # Now get the start and end times.
         start, end = times.split('.')
         # Convert them from strings to floating point seconds.
         # Minutes:Seconds:Frames
         # 75 frames per second.
         start_split = [int(x) for x in start.split(':')]
         if(len(start_split) != 3):
            start_time = 0
         else:
            start_time = start_split[0]*60 + start_split[1] + start_split[2]/75
         end_split = [int(x) for x in end.split(':')]
         if(len(end_split) != 3):
            # Nothing longer than 10 hours.
            end_time = 3600*10
         else:
            end_time = end_split[0]*60 + end_split[1] + end_split[2]/75
         with self.rwlock:
            # Hold a file handle for the actual file.
            fd = os.open(path, flags, *args, **pargs)
            # If we've already processed this file and still have it in memory.
            if(raw_path in self._open_subtracks):
               # Update the stored info.
               (positions, audio, count, last_access) = self._open_subtracks[raw_path]
               count += 1
               last_access = time.time()
               positions[fd] = 0
               self._open_subtracks[raw_path] = (positions, audio, count, last_access)
               # Return the file handle.
               return fd
            # Otherwise, we have to process the FLAC file to extract the track.
            # Open the file with FFMPEG.
            track = ffmpeg.input(path)
            # Set the output to convert to a wave file and pipe to stdout.
            # Trim it to start at start_time and end at end_time.
            output = track.output('pipe:', ss=start_time, to=end_time, format='wav')
            # Do the conversion. Capture stdout into a buffer.
            out, _ = output.run(capture_stdout=True)
            # Convert the buffer to a numpy array. Use bytes to access just like a
            # normal file.
            audio = numpy.frombuffer(out, numpy.uint8)
            # Store some extra info in addition to the wave file.
            positions = {}
            positions[fd] = 0
            count = 1
            last_access = time.time()
            # Keep a copy of the data in memory.
            self._open_subtracks[raw_path] = (positions, audio, count, last_access)
            # Define a function that will clean up the memory use once it's no longer needed.
            def cleanup():
               (positions, audio, count, last_access) = self._open_subtracks[raw_path]
               # Wait for all open instances of this file to be closed.
               # Also ensure there has been no access to the data for 60 seconds.
               while(count > 0 or (time.time() - last_access < 60)):
                  with(self.rwlock):
                     (positions, audio, count, last_access) = self._open_subtracks[raw_path]
                  # Check every 5 seconds.
                  time.sleep(5)
               # Delete the entry. This removes all references to the data which allows
               # garbage collection to clean up when appropriate.
               with(self.rwlock):
                  del self._open_subtracks[raw_path]
            # Start a thread running that function.
            thread = threading.Thread(target=cleanup)
            thread.start()
            # Return the file handle.
            return fd
      else:
         # With any other file, just pass it along normally.
         # This allows FLAC files to be read with a FLACCue path.
         # Note that you do not want to run this as root as this will
         # give anyone read access to any file.
         with self.rwlock:
            return os.open(path, flags, *args, **pargs)

   def read(self, path, size, offset, fh):
      with self.rwlock:
         if(path in self._open_subtracks):
            # For files we've processed.
            positions, audio, count, last_access = self._open_subtracks[path]
            # Store the current offset.
            positions[fh] = offset
            # Update the last accessed time.
            last_access = time.time()
            # Update the stored data.
            self._open_subtracks[path] = (positions, audio, count, last_access)
            # Return the data requested.
            return bytes(audio[positions[fh]:positions[fh]+size])
         else:
            # For all other files, just access it normally.
            os.lseek(fh, offset, 0)
            return os.read(fh, size)

   def readdir(self, path, fh):
      path = self.clean_path(path)
      return ['.', '..'] + os.listdir(path)

   def readlink(self, path, *args, **pargs):
      path = self.clean_path(path)
      return os.readlink(path, *args, **pargs)

   def release(self, path, fh):
      with(self.rwlock):
         # If we're closing a FLACCue file...
         if(path in self._open_subtracks):
            positions, audio, count, last_access = self._open_subtracks[path]
            # Delete the file handle from the stored list.
            del positions[fh]
            # Decrement the access count.
            count -= 1
            # Update the last access time.
            last_access = time.time()
            # Update the stored info.
            self._open_subtracks[path] = (positions, audio, count, last_access)
         # Close the OS reference to the file.
         return os.close(fh)

   def statfs(self, path):
      path = self.clean_path(path)
      stv = os.statvfs(path)
      return dict((key, getattr(stv, key)) for key in (
         'f_bavail', 'f_bfree', 'f_blocks', 'f_bsize', 'f_favail',
         'f_ffree', 'f_files', 'f_flag', 'f_frsize', 'f_namemax'))

if __name__ == '__main__':
   import argparse
   parser = argparse.ArgumentParser()
   parser.add_argument('root')
   parser.add_argument('mount')
   args = parser.parse_args()

   #logging.basicConfig(level=logging.DEBUG)
   fuse = FUSE(
      FLACCue(args.root), args.mount, foreground=True, allow_other=True)
