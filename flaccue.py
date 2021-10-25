#!/usr/bin/env python3

""" FUSE filesystem to parse .cue files into separate tracks.

Note that you do not want to run this as root as this will
give anyone read access to any file by just prepending /flaccue/.
"""


import os

import ffmpeg
import mutagen
import numpy
import time
import threading

import sys
sys.path.insert(0, '.')


import fuse


def read_cue(file):
    """Parse the Cue sheet to get the desired info."""
    # Read the full Cue file.
    try:
        with open(file, 'r') as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        with open(file, 'r', encoding='utf-16') as f:
            lines = f.readlines()
    cue = {}
    cue['Files'] = {}
    # Line index. We don't use a for loop as we will
    # read multiple lines for information.
    i = 0
    try:
        while(True):
            # We have a FILE specification in the Cue sheet.
            if(lines[i].startswith('FILE')):
                # Get the filename.
                filename = lines[i].split('"')[1]
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


def get_cue_files(cue_file):
    info = read_cue(cue_file)
    to_remove = []
    to_add = {}
    meta = {}
    # Get all files mentioned in the Cue sheet.
    cuefiles = info['Files']
    # Get the album information.
    album = info['TITLE']
    album_artist = info['PERFORMER']
    if(album_artist == ''):
        # No listed album artist. Use the artist from the first
        # track of the first file.
        try:
            first_file = list(cuefiles.keys())[0]
            album_artist = cuefiles[first_file]['Tracks'][1]['PERFORMER']
        except KeyError:
            album_artist = 'Unknown'
    for file in cuefiles:
        # Get the full file path.
        full_file = os.path.join(os.path.dirname(cue_file), file)
        extension = os.path.splitext(file)[1]
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
            disc = ''

        # Split into tracks.
        track_info = cuefiles[file]['Tracks']
        start_time = '00:00:00'
        end_time = '00:00:00'
        # Handle each track.
        for track in track_info:
            title = track_info[track]['TITLE']
            try:
                artist = track_info[track]['PERFORMER']
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
            track_file = f'{artist} - {album} - {disc}{track:02d} {title}.wav'
            track_file = track_file.replace('/', ' ')
            to_add[track_file] = full_file.replace(extension, f'.flaccuesplit.{start_time}.{end_time}{extension}')
            # A bit of a hack needed for ffmpeg interfacing.
            meta[track_file] = {'metadata:g:1': f'artist={artist}',
                                'metadata:g:2': f'album={album}',
                                'metadata:g:3': f'disc={disc}',
                                'metadata:g:4': f'track={track}',
                                'metadata:g:5': f'title={title}',
                                }
        # Remove the FLAC file from the list to parse.
        to_remove.append(file)
    return to_add, meta, to_remove


def clean_path(path):
    """Get a file path for the FLAC file from a FLACCue path.

    Notes
    -----
    Files accessed through FLACCue will still read normally.
    We just need to trim off the song times.
    """
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


def find_cue_path(path):
    meta = None
    if(not os.path.exists(path)):
        dir_path = clean_path(os.path.dirname(path))
        files = os.listdir(dir_path)
        for cue_file in files:
            if(os.path.splitext(cue_file)[1] == '.cue'):
                try:
                    to_add, metadata, to_remove = get_cue_files(os.path.join(dir_path, cue_file))
                    base_path = os.path.basename(path)
                    if(base_path in to_add):
                        path = to_add[base_path]
                        meta = metadata[base_path]
                        break
                except Exception:
                    import traceback
                    traceback.print_exc()
    return path, meta


class FLACCue(fuse.LoggingMixIn, fuse.Operations):
    """FUSE filesystem to parse .cue files into separate tracks."""

    def __init__(self, root):
        """Initialize the filesystem for the root path."""
        self.root = os.path.realpath(root)
        self.rwlock = threading.RLock()
        self._open_subtracks = {}

    def __call__(self, op, path, *args):
        """Transfer any call to this filesystem to include the root path."""
        return super(FLACCue, self).__call__(op, os.path.join(self.root, path), *args)

    def getattr(self, path, fh=None):
        """Get the attributes of the file path.

        If it's one of the FLACCue paths, we need to adjust the file size to be
        appropriate for the shortened data.
        """
        path, meta = find_cue_path(path)
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
            except Exception:
                import traceback
                traceback.print_exc()
        # Otherwise, just get the normal info.
        path = clean_path(path)
        st = os.lstat(path)
        return dict((key, getattr(st, key)) for key in (
            'st_atime', 'st_ctime', 'st_gid', 'st_mode', 'st_mtime',
            'st_nlink', 'st_size', 'st_uid'))

    getxattr = None

    listxattr = None

    def open(self, path, flags, *args, **pargs):
        """Open the specified path."""
        # We don't want FLACCue messing with actual data.
        # Only allow Read-Only access.
        if((flags | os.O_RDONLY) == 0):
            raise ValueError('Can only open files read-only.')
        raw_path = path
        path, meta = find_cue_path(path)
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
                    if(self._open_subtracks[raw_path] is not None):
                        # Update the stored info.
                        (positions, audio, count, last_access) = self._open_subtracks[raw_path]
                        count += 1
                        last_access = time.time()
                        positions[fd] = 0
                        self._open_subtracks[raw_path] = (positions, audio, count, last_access)
                        # Return the file handle.
                        return fd
                    else:
                        # We're still processing this track. Wait for it to finish.
                        process = False
                else:
                    # This is a new track to process.
                    process = True
                    self._open_subtracks[raw_path] = None
            if(process):
                # Otherwise, we have to process the FLAC file to extract the track.
                # Open the file with FFMPEG.
                track = ffmpeg.input(path)
                # Set the output to convert to a wave file and pipe to stdout.
                # Trim it to start at start_time and end at end_time.
                output = track.output('pipe:', ss=start_time, to=end_time, format='wav', **meta)
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
                    # Count isn't working for some reason. Just use last_access time.
                    # while(count > 0 or (time.time() - last_access < 60)):
                    while(time.time() - last_access < 60):
                        with(self.rwlock):
                            (positions, audio, count, last_access) = self._open_subtracks[raw_path]
                        # Check every 5 seconds.
                        time.sleep(5)
                    # Delete the entry. This removes all references to the data which allows
                    # garbage collection to clean up when appropriate.
                    with(self.rwlock):
                        del self._open_subtracks[raw_path]
                    print(f'{raw_path} closed.')

                # Start a thread running that function.
                thread = threading.Thread(target=cleanup)
                thread.start()
                # Return the file handle.
                return fd
            else:
                acquired = False
                try:
                    while(True):
                        self.rwlock.acquire()
                        acquired = True
                        if(self._open_subtracks[raw_path] is not None):
                            break
                        self.rwlock.release()
                        acquired = False
                        time.sleep(0.1)
                        # Update the stored info.
                        (positions, audio, count, last_access) = self._open_subtracks[raw_path]
                        count += 1
                        last_access = time.time()
                        positions[fd] = 0
                        self._open_subtracks[raw_path] = (positions, audio, count, last_access)
                        # Return the file handle.
                        return fd
                finally:
                    if(acquired):
                        self.rwlock.release()
        else:
            # With any other file, just pass it along normally.
            # This allows FLAC files to be read with a FLACCue path.
            # Note that you do not want to run this as root as this will
            # give anyone read access to any file.
            with self.rwlock:
                return os.open(path, flags, *args, **pargs)

    def read(self, path, size, offset, fh):
        """Read data from the path."""
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
        """Read the contents of the directory."""
        path = clean_path(path)
        files = os.listdir(path)
        i = 0
        while(i < len(files)):
            if(os.path.splitext(files[i])[1] == '.cue'):
                try:
                    cue_file = files.pop(i)
                    to_add, meta, to_remove = get_cue_files(os.path.join(path, cue_file))
                    files.extend(to_add.keys())
                    for f in to_remove:
                        files.remove(f)
                except Exception:
                    import traceback
                    traceback.print_exc()
            else:
                i += 1

        return ['.', '..'] + files

    def readlink(self, path, *args, **pargs):
        """Read a file link."""
        path, meta = find_cue_path(path)
        path = clean_path(path)
        return os.readlink(path, *args, **pargs)

    def release(self, path, fh):
        """Release the file handle."""
        path, meta = find_cue_path(path)
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
        """Get the dictionary of filesystem stats."""
        path, meta = find_cue_path(path)
        path = clean_path(path)
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

    fuse_obj = fuse.FUSE(FLACCue(args.root), args.mount, foreground=True, allow_other=True)
