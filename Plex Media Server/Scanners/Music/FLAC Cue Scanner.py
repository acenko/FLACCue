import AudioFiles

from flaccuelib import FLACCueParse

def Scan(path, files, mediaList, subdirs, language=None, root=None):
   """Handle .cue files.
   Find any Cue files in the input list. Remove any files handled by the Cue
   file. Handle any remaining files normally.
   """
   FLACCueParse(path, files, mediaList, subdirs, language=language, root=root)
   
   # Scan for other audio files, including those that failed to process correctly.
   AudioFiles.Scan(path, files, mediaList, subdirs, root=root)

   # Read tags, etc. and build up the mediaList
   AudioFiles.Process(path, files, mediaList, subdirs, language=language, root=root)

