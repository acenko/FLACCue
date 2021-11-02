#!/usr/bin/env python3

"""FUSE filesystem to parse .cue files into separate tracks.

Note that you do not want to run this as root as this will
give anyone read access to any file by just prepending /flaccue/.
"""


import os
import tempfile

import ffmpeg
import mutagen
import numpy
import time
import threading

import sys
sys.path.insert(0, '.')


import fuse


encodings_to_test = [
    'ascii',
    'utf_8',
    'utf_16',
    'utf_32',
    'latin_1',
    'big5',
    'big5hkscs',
    'cp037',
    'cp273',
    'cp424',
    'cp437',
    'cp500',
    'cp720',
    'cp737',
    'cp775',
    'cp850',
    'cp852',
    'cp855',
    'cp856',
    'cp857',
    'cp858',
    'cp860',
    'cp861',
    'cp862',
    'cp863',
    'cp864',
    'cp865',
    'cp866',
    'cp869',
    'cp874',
    'cp875',
    'cp932',
    'cp949',
    'cp950',
    'cp1006',
    'cp1026',
    'cp1125',
    'cp1140',
    'cp1250',
    'cp1251',
    'cp1252',
    'cp1253',
    'cp1254',
    'cp1255',
    'cp1256',
    'cp1257',
    'cp1258',
    'cp65001',
    'euc_jp',
    'euc_jis_2004',
    'euc_jisx0213',
    'euc_kr',
    'gb2312',
    'gbk',
    'gb18030',
    'hz',
    'iso2022_jp',
    'iso2022_jp_1',
    'iso2022_jp_2',
    'iso2022_jp_2004',
    'iso2022_jp_3',
    'iso2022_jp_ext',
    'iso2022_kr',
    'iso8859_2',
    'iso8859_3',
    'iso8859_4',
    'iso8859_5',
    'iso8859_6',
    'iso8859_7',
    'iso8859_8',
    'iso8859_9',
    'iso8859_10',
    'iso8859_11',
    'iso8859_13',
    'iso8859_14',
    'iso8859_15',
    'iso8859_16',
    'johab',
    'koi8_r',
    'koi8_t',
    'koi8_u',
    'kz1048',
    'mac_cyrillic',
    'mac_greek',
    'mac_iceland',
    'mac_latin2',
    'mac_roman',
    'mac_turkish',
    'ptcp154',
    'shift_jis',
    'shift_jis_2004',
    'shift_jisx0213',
    'utf_32_be',
    'utf_32_le',
    'utf_16_be',
    'utf_16_le',
    'utf_7',
    'utf_8_sig',
    ]


def read_cue(file, verbose=False):
    """Parse the Cue sheet to get the desired info."""
    # Read the full Cue file.
    if(verbose):
        print(f'Parsing {file}...', flush=True)
    lines = None
    for encoding in encodings_to_test:
        try:
            with open(file, 'r', encoding=encoding) as f:
                lines = f.readlines()
            if(verbose):
                print(f'Parsed using "{encoding}" encoding.', flush=True)
            break
        except UnicodeError:
            pass

    if(lines is None):
        raise UnicodeError('Unable to find appropriate encoding for input file.')

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


class FLACCue(fuse.LoggingMixIn, fuse.Operations):
    """FUSE filesystem to parse .cue files into separate tracks."""

    def __init__(self, root, mount, format='flac', use_tempfile=True, cache_cue=True, verbose=False):
        """Initialize the filesystem for the root path.

        Parameters
        ----------
        root : str
            The root directory mirrored by this filesystem.
        mount : str
            The mount point for this filesystem.
        format : str
            The output format for any extracted cue tracks.
            Most likely 'flac' or 'wav'.
        use_tempfile : bool
            If True, create a temporary file for the output
            of ffmpeg, allowing ffmpeg to fix header information
            and similar after encoding the track. Otherwise,
            use stdout from ffmpeg so we never need to write
            to disk.
        cache_cue : bool
            If True, cache parsed cue files. Otherwise, parse
            cue files every time the filesystem accesses them.
        verbose : bool
            If True, print out extra information that may be useful
            for debugging.
        """
        self.root = os.path.realpath(root)
        self.mount = os.path.realpath(mount)
        self.rwlock = threading.RLock()
        self._open_subtracks = {}
        self._format = format
        self._verbose = verbose
        self._use_tempfile = use_tempfile
        if(cache_cue):
            self._cue_cache = {}
            self._track_cache = {}

    def __call__(self, op, path, *args):
        """Transfer any call to this filesystem to include the root path."""
        return super(FLACCue, self).__call__(op, os.path.join(self.root, path), *args)

    def get_cue_files(self, cue_file, verbose=False):
        """Get details on the files referenced by the cue file.

        Parameters
        ----------
        cue_file : str
            The cue filename.
        verbose : bool (optional)
            If True, print out extra information on the parsed
            cue file.

        Returns
        -------
        to_add : dict
            Dictionary of human friendly filename for tracks
            indexing filenames for extracting the tracks from
            the raw audio files.
        meta : dict
            Dictionary of metadata for each file generated from
            the cue sheet. This is intended to pass to ffmpeg
            during processing to update the metadata in the
            output header.
        to_remove : list
            List of files referenced by the cue file. These are
            intended for removal from the directory listing.
        """
        try:
            if(cue_file in self._cue_cache):
                return self._cue_cache[cue_file]
        except (AttributeError, NameError, TypeError):
            # Cue cache disabled.
            pass
        info = read_cue(cue_file, verbose=verbose)
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
                track_file = f'{artist} - {album} - {disc}{track:02d} {title}.{self._format}'
                track_file = track_file.replace('/', ' ')
                to_add[track_file] = self.mount + full_file + f'.flaccuesplit.{start_time}.{end_time}.{self._format}'
                # A bit of a hack needed for ffmpeg interfacing.
                meta[track_file] = {'metadata:g:1': f'artist={artist}',
                                    'metadata:g:2': f'album={album}',
                                    'metadata:g:3': f'disc={disc}',
                                    'metadata:g:4': f'track={track}',
                                    'metadata:g:5': f'title={title}',
                                    }
            # Remove the FLAC file from the list to parse.
            to_remove.append(file)
        try:
            self._cue_cache[cue_file] = (to_add, meta, to_remove)
        except (AttributeError, NameError, TypeError):
            # Not using caching.
            pass
        return to_add, meta, to_remove

    def clean_path(self, path):
        """Get a file path for the FLAC file from a FLACCue path.

        Notes
        -----
        Files accessed through FLACCue will still read normally.
        We just need to trim off the song times.
        """
        if('.flaccuesplit.' in path):
            path, flaccue_details = path.split('.flaccuesplit.')
        if(path.startswith(self.mount)):
            # Strip off the mount point.
            path = path[len(self.mount):]
        return path

    def find_cue_path(self, path, verbose=False):
        """Find the path necessary for extracting tracks using the cue sheets.

        Parameters
        ----------
        path : str
            The path to filter. If the file exists or already includes the
            flaccuesplit details, it is passed through directly. Otherwise,
            search the cue files in the path directory for tracks matching
            the path.
        verbose : bool (optional)
            If True, print any filename conversion details.

        Returns
        -------
        path : str
            A pathname that can be read from disk.
        meta : dict or None
            Metadata associated with the input path. Only provided
            when the path is created from a cue file.
        """
        meta = None
        if('.flaccuesplit.' not in path and not os.path.exists(path)):
            try:
                path, meta = self._track_cache[path]
            except (AttributeError, NameError, TypeError, KeyError):
                # Not caching or not yet cached.
                raw_path = path
                dir_path = self.clean_path(os.path.dirname(path))
                files = os.listdir(dir_path)
                for cue_file in files:
                    if(os.path.splitext(cue_file)[1] == '.cue'):
                        try:
                            # Don't use verbose here. Overly spammy.
                            to_add, metadata, to_remove = self.get_cue_files(os.path.join(dir_path, cue_file))
                            base_path = os.path.basename(path)
                            if(base_path in to_add):
                                path = to_add[base_path]
                                meta = metadata[base_path]
                                break
                        except Exception:
                            print(f'Error parsing {cue_file}:', file=sys.stderr, flush=True)
                            import traceback
                            traceback.print_exc()
                try:
                    self._track_cache[raw_path] = (path, meta)
                except (AttributeError, NameError, TypeError):
                    # Not caching.
                    pass
                if(verbose):
                    print(f'{raw_path} -> {path}', flush=True)
        return path, meta

    def getattr(self, path, fh=None):
        """Get the attributes of the file path.

        If it's one of the FLACCue paths, we need to adjust the file size to be
        appropriate for the shortened data.
        """
        path, meta = self.find_cue_path(path)
        if('.flaccuesplit.' in path):
            try:
                raw_path = path
                path, flaccue_details = path.split('.flaccuesplit.')
                path = self.clean_path(path)
                times, extension = os.path.splitext(flaccue_details)
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
                # Ensure the mode shows the file as readable.
                toreturn['st_mode'] = toreturn['st_mode'] | 0o444
                return toreturn
            except Exception:
                print(f'Error getting attributes for {raw_path}:', file=sys.stderr, flush=True)
                import traceback
                traceback.print_exc()
        # Otherwise, just get the normal info.
        path = self.clean_path(path)
        st = os.lstat(path)
        toreturn = dict((key, getattr(st, key)) for key in (
            'st_atime', 'st_ctime', 'st_gid', 'st_mode', 'st_mtime',
            'st_nlink', 'st_size', 'st_uid'))
        # Ensure the mode shows the file as readable.
        toreturn['st_mode'] = toreturn['st_mode'] | 0o444
        return toreturn

    def open(self, path, flags, *args, **pargs):
        """Open the specified path."""
        # We don't want FLACCue messing with actual data.
        # Only allow Read-Only access.
        if((flags | os.O_RDONLY) == 0):
            raise ValueError('Can only open files read-only.')
        raw_path = path
        path, meta = self.find_cue_path(path, verbose=self._verbose)
        # Handle the FLACCue files.
        if('.flaccuesplit.' in path):
            # Get a path to the actual file name.
            # Note that files accessed through FLACCue will
            # still read normally--we just need to trim off the song
            # times and fix the file extension.
            path, flaccue_details = path.split('.flaccuesplit.')
            path = self.clean_path(path)
            times, extension = os.path.splitext(flaccue_details)

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

            # Hold a file handle for the actual file.
            fd = os.open(path, flags, *args, **pargs)
            with self.rwlock:
                # If we've already processed this file and still have it in memory.
                if(raw_path in self._open_subtracks):
                    if('Audio' in self._open_subtracks[raw_path]):
                        if(self._open_subtracks[raw_path]['Audio'] is not None):
                            # Update the stored info.
                            self._open_subtracks[raw_path]['Last Access'] = time.time()
                            self._open_subtracks[raw_path]['Positions'][fd] = 0
                            # Return the file handle.
                            return fd
                        else:
                            # We're still processing this track. Wait for it to finish.
                            process = False
                            self._open_subtracks[raw_path]['Positions'][fd] = 0
                    else:
                        # Reloading the data.
                        process = True
                        self._open_subtracks[raw_path]['Audio'] = None
                        self._open_subtracks[raw_path]['Extra Handles'].append(fd)
                else:
                    # This is a new track to process.
                    process = True
                    self._open_subtracks[raw_path] = {'Positions': {fd: 0},
                                                      'Last Access': time.time(),
                                                      'Audio': None,
                                                      'Extra Handles': [],  # Store extra handles for auto reopens.
                                                      }
            if(process):
                if(self._verbose):
                    print(f'Loading {raw_path}...', flush=True)
                # Otherwise, we have to process the FLAC file to extract the track.
                # Open the file with FFMPEG.
                track = ffmpeg.input(path)
                if(self._use_tempfile):
                    # Use a tempfile so ffmpeg can update metadata after finishing
                    # compression.
                    with tempfile.TemporaryDirectory() as temp:
                        filename = os.path.join(temp, f'temp.{self._format}')
                        # Set the output to convert to a temporary file.
                        # Trim it to start at start_time and end at end_time.
                        output = track.output(filename, ss=start_time, to=end_time,
                                              format=self._format, **meta)
                        # Do the conversion.
                        output.run()
                        # Read the temporary file in as a bytes buffer.
                        with open(filename, 'rb') as f:
                            data = f.read()
                else:
                    # Set the output to convert to a wave file and pipe to stdout.
                    # Trim it to start at start_time and end at end_time.
                    output = track.output('pipe:', ss=start_time, to=end_time,
                                          format=self._format, **meta)
                    # Do the conversion. Capture stdout into a buffer.
                    data, _ = output.run(capture_stdout=True)
                    # Convert the buffer to a numpy array. Use bytes to access just like a
                    # normal file.
                # Convert the buffer to a numpy array. Use bytes to access just like a
                # normal file.
                audio = numpy.frombuffer(data, dtype=numpy.uint8)

                with(self.rwlock):
                    # Keep a copy of the data in memory.
                    self._open_subtracks[raw_path]['Last Access'] = time.time()
                    self._open_subtracks[raw_path]['Audio'] = audio

                # Define a function that will clean up the memory use once it hasn't been
                # used for a while.
                def cleanup():
                    # Wait until there has been no access to the data for 60 seconds.
                    while(True):
                        with(self.rwlock):
                            # Do this all within the same lock to avoid potential changes
                            # in between the check and deletion.
                            if(time.time() - self._open_subtracks[raw_path]['Last Access'] > 60):
                                # Delete the audio entry. This removes references to the data which
                                # allows garbage collection to clean up when appropriate.
                                # Always clean up any extra handles. Do so outside the lock.
                                extra_handles = self._open_subtracks[raw_path].pop('Extra Handles')
                                if(len(self._open_subtracks[raw_path]['Positions']) > 0):
                                    # Still have open file handles.
                                    # Just delete the audio data.
                                    open_handles = len(self._open_subtracks[raw_path]['Positions'])
                                    del self._open_subtracks[raw_path]['Audio']
                                    self._open_subtracks[raw_path]['Extra Handles'] = []
                                else:
                                    open_handles = 0
                                    del self._open_subtracks[raw_path]
                                break
                        # Check every 5 seconds.
                        time.sleep(5)
                    # Clean up the extra handles here. No need to do so while locked.
                    for fd in extra_handles:
                        os.close(fd)
                    if(self._verbose):
                        print(f'{raw_path} closed. {open_handles} file handles open.', flush=True)

                # Start a thread running that function.
                thread = threading.Thread(target=cleanup)
                thread.start()
                # Return the file handle.
                return fd
            else:
                # Wait for the previous open call to open the file.
                while(True):
                    with(self.rwlock):
                        # Ensure we keep the last access time fresh so we don't
                        # close the file before this is done.
                        self._open_subtracks[raw_path]['Last Access'] = time.time()
                        if(self._open_subtracks[raw_path]['Audio'] is not None):
                            break
                    time.sleep(0.1)
                # Return the file handle.
                return fd
        else:
            # With any other file, just pass it along normally.
            # This allows FLAC files to be read with a FLACCue path.
            # Note that you do not want to run this as root as this will
            # give anyone read access to any file.
            return os.open(path, flags, *args, **pargs)

    def read(self, path, size, offset, fh):
        """Read data from the path."""
        with self.rwlock:
            if(path in self._open_subtracks):
                # Update the last accessed time.
                self._open_subtracks[path]['Last Access'] = time.time()
                # Get the info for processed files.
                info = self._open_subtracks[path]
            else:
                info = None
        if(info is None):
            # For all non-FLACCue files, just access it normally.
            os.lseek(fh, offset, 0)
            return os.read(fh, size)
        elif('Audio' not in info):
            # Start a thread to reload the data if needed.
            thread = threading.Thread(target=self.open,
                                      args=(path, os.O_RDONLY,))
            thread.start()
        # Ensure the data is processed and available.
        while(True):
            with(self.rwlock):
                # Ensure we keep the last access time fresh so we don't
                # close the file before this is done.
                self._open_subtracks[path]['Last Access'] = time.time()
                if(self._open_subtracks[path]['Audio'] is not None):
                    # Store the requested offset.
                    self._open_subtracks[path]['Positions'][fh] = offset
                    # Store the data.
                    audio = self._open_subtracks[path]['Audio']
                    break
            time.sleep(0.1)
        # Return the data requested.
        if(offset > len(audio)):
            # If we're looking near the end of the file,
            # handle the fact that compression could change the size.
            reported_size = self.getattr(path)['st_size']
            if(offset < reported_size):
                offset = len(audio) - (reported_size - offset)
        return audio[offset:offset+size].tobytes()

    def readdir(self, path, fh):
        """Read the contents of the directory."""
        path = self.clean_path(path)
        files = os.listdir(path)
        i = 0
        while(i < len(files)):
            if(os.path.splitext(files[i])[1] == '.cue'):
                cue_file = files.pop(i)
                try:
                    to_add, meta, to_remove = self.get_cue_files(
                        os.path.join(path, cue_file), verbose=self._verbose)
                    files.extend(to_add.keys())
                    for f in to_remove:
                        files.remove(f)
                except Exception:
                    print(f'Error parsing {cue_file}:', file=sys.stderr, flush=True)
                    import traceback
                    traceback.print_exc()
            else:
                i += 1

        return ['.', '..'] + files

    def release(self, path, fh):
        """Release the file handle."""
        path, meta = self.find_cue_path(path)
        with(self.rwlock):
            # If we're closing a FLACCue file...
            if(path in self._open_subtracks):
                # Delete the file handle from the stored list.
                del self._open_subtracks[path]['Positions'][fh]
        # Close the OS reference to the file.
        return os.close(fh)

    def statfs(self, path):
        """Get the dictionary of filesystem stats."""
        path, meta = self.find_cue_path(path)
        path = self.clean_path(path)
        stv = os.statvfs(path)
        return dict((key, getattr(stv, key)) for key in (
            'f_bavail', 'f_bfree', 'f_blocks', 'f_bsize', 'f_favail',
            'f_ffree', 'f_files', 'f_flag', 'f_frsize', 'f_namemax'))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('root', help='The location to replicate with .cue parsing.')
    parser.add_argument('mount', help='The location to mount the FUSE filesystem.')
    parser.add_argument('-f', '--format',
                        dest='format', type=str,
                        default='flac',
                        help='The audio file format to use for the split files.')
    parser.add_argument('-v', '--verbose',
                        dest='verbose', action='store_true',
                        help='Whether to print verbose messages.')
    args = parser.parse_args()

    fuse_obj = fuse.FUSE(FLACCue(args.root, args.mount, format=args.format, verbose=args.verbose),
                         args.mount, foreground=True, allow_other=True)
