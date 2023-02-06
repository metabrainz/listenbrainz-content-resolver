import os
import datetime
import sys

from unidecode import unidecode

from lb_content_resolver.formats import mp3, flac
from lb_content_resolver.schema import schema
from lb_content_resolver.playlist import convert_jspf_to_m3u
from whoosh.index import create_in, open_dir
from whoosh.qparser import QueryParser, FuzzyTermPlugin
from whoosh.fields import *


SUPPORTED_FORMATS = ["mp3", "flac"]

class ContentResolver:
    ''' 
    Scan a given path and enter/update the metadata in the search index
    '''

    def __init__(self, index_dir):
        self.ix = None
        self.index_dir = index_dir

    def create(self):

        try:
            os.mkdir(self.index_dir)
        except OSError as err:
            print("Could not create index directory: %s (%s)" % (self.index_dir, err))
            return

        try:
            ix = create_in(self.index_dir, schema)
        except FileNotFoundError as err:
            print("Could not create index: %s (%s)" % (self.index_dir, err))
            return

    def open_index(self):
        try:
            self.ix = open_dir(self.index_dir)
        except FileNotFoundError:
            print("%s index dir not found. Create one with the create-index command." % self.index_dir)

    def close_index(self):
        self.ix.close()
        self.ix = None

    def scan(self, music_dir):
        self.music_dir = os.path.abspath(music_dir)

        # Keep some stats
        self.total = 0
        self.not_changed = 0
        self.updated = 0
        self.added = 0
        self.error = 0
        self.skipped = 0

        self.open_index()
        self.writer = self.ix.writer()

        self.traverse("")

        self.writer.commit()
        self.writer = None
        self.close_index()

        print("Checked %s tracks:" % self.total)
        print("  %5d tracks not changed since last run" % self.not_changed)
        print("  %5d tracks added" % self.added)
        print("  %5d tracks updated" % self.updated)
        print("  %5d tracks could not be read" % self.error)
        print("  %5d files are not supported" % self.skipped)
        if self.total != self.not_changed + self.updated + self.added + self.error + self.skipped:
            print("And for some reason these numbers don't add up to the total number of tracks. Hmmm.")


    def traverse(self, relative_path):

        if not relative_path:
            fullpath = self.music_dir
        else:
            fullpath = os.path.join(self.music_dir, relative_path)

        for f in os.listdir(fullpath):
            if f in ['.', '..']: 
                continue

            new_relative_path = os.path.join(relative_path, f)
            new_full_path = os.path.join(self.music_dir, new_relative_path)
            if os.path.isfile(new_full_path): 
                self.add(new_relative_path)
            if os.path.isdir(new_full_path): 
                if not self.traverse(new_relative_path):
                    return False

        return True

    def encode_string(self, text):
        return unidecode(re.sub(" +", " ", re.sub(r'[^\w ]+', '', text)).strip().lower())

    def resolve_recording(self, artist_name, recording_name, distance=2):

        query = "%s~%d %s~%d" % (self.encode_string(artist_name),
                                 distance,
                                 self.encode_string(recording_name),
                                 distance)
        self.open_index()

        ret = []
        with self.ix.searcher() as searcher:
            parser = QueryParser("lookup", self.ix.schema)
            parser.add_plugin(FuzzyTermPlugin())
            query = parser.parse(query)
            for result in searcher.search(query):
                ret.append(dict(result))

        return ret

    def resolve_playlist(self, jspf_playlist, m3u_playlist):
        return convert_jspf_to_m3u(self, jspf_playlist, m3u_playlist)

    def lookup_metadata(self, file_path):
        """
            Assumes index is open
        """

        # This function does not work -- no results are ever returned.
        # Likely connected to: 
        #   https://github.com/mchaput/whoosh/issues/29
        # For this reason, tracks will always be added, not updated. Lame
        with self.ix.searcher() as searcher:
            query = QueryParser("file_path", self.ix.schema).parse(file_path)
            for result in searcher.search(query):
                print(result)
                return dict(result)

        return None

    def index_metadata(self, mdata):
        encoded_artist = self.encode_string(mdata["artist_name"])
        encoded_recording = self.encode_string(mdata["recording_name"])
        encoded_release = self.encode_string(mdata["release_name"])
        self.writer.add_document(
            file_path=mdata["file_path"],
            recording_mbid=mdata['recording_mbid'], 
            recording_name=mdata['recording_name'], 
            artist_name=mdata['artist_name'], 
            artist_mbid=mdata['artist_mbid'], 
            release_name=mdata['release_name'], 
            release_mbid=mdata['release_mbid'], 
            track_num=mdata['track_num'], 
            duration=mdata['duration'], 
            lookup=f"{encoded_artist} {encoded_recording}",
            lookup_release=f"{encoded_artist} {encoded_recording} {encoded_release}"
        )

    def delete_metadata(self, mdata):
        self.writer.delete_by_term("file_path", mdata["file_path"])


    def add_file_to_index(self, relative_path, format, mtime):
        file_path = os.path.join(self.music_dir, relative_path)

        # If the record exists, delete it. Sadly, there seems to be a
        # a bug in whoosh, so this doesnt't work. :( See lookup_metadata for more details
        result = self.lookup_metadata(file_path)
        if result is not None:
            if result["mtime"] == mtime:
                return result, "unchanged"

            self.delete_metadata(mdata, relative_path)
            status = "updated"
        else:
            status = "added"

        # We've never seen this before, or it was updated since we last saw it.
        if format == "mp3":
            mdata = mp3.read(file_path, mtime)
        elif format == "flac":
            mdata = flac.read(file_path, mtime)

        mdata["file_path"] = file_path

        # now add the record
        self.index_metadata(mdata)

        return status


    def add(self, relative_path):

        fullpath = os.path.join(self.music_dir, relative_path)
        self.total += 1

        # Check to see if the file in question has changed since the last time
        # we looked at it. If not, skip it for speed
        stats = os.stat(fullpath)
        ts = datetime.datetime.fromtimestamp(stats[8])

        base, ext = os.path.splitext(relative_path)
        ext = ext.lower()[1:]
        base = os.path.basename(relative_path)
        if ext not in SUPPORTED_FORMATS:
            print("    ? %s" % base)
            self.skipped += 1
            return

        # read the file's last modified time to avoid re-reading tags
        stats = os.stat(fullpath)
        ts = datetime.datetime.fromtimestamp(stats[8])

        status = self.add_file_to_index(relative_path, ext, ts)
        if status == "updated":
            print("    U %s" % base)
            self.updated += 1
        elif status == "added":
            print("    A %s" % base)
            self.added += 1
        else:
            self.error += 1
            print("    E %s" % base)
