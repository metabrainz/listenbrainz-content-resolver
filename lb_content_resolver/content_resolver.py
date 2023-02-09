import os
import datetime
import sys

from unidecode import unidecode
import peewee


from lb_content_resolver.model.database import db, setup_db
from lb_content_resolver.model.recording import Recording
from lb_content_resolver.fuzzy_index import FuzzyIndex

from lb_content_resolver.formats import mp3, m4a, flac, ogg_vorbis, wma
from lb_content_resolver.schema import schema
from lb_content_resolver.playlist import convert_jspf_to_m3u

SUPPORTED_FORMATS = ["flac", "ogg", "mp3", "m4a", "wma"]


class ContentResolver:
    ''' 
    Scan a given path and enter/update the metadata in the search index
    '''

    def __init__(self, index_dir):
        self.index_dir = index_dir
        self.db_file = os.path.join(index_dir, "lb_resolve.db")

    def create(self):
        try:
            os.mkdir(self.index_dir)
        except OSError as err:
            print("Could not create index directory: %s (%s)" % (self.index_dir, err))
            return

        setup_db(self.db_file)
        db.connect()
        db.create_tables([Recording])

    def open_db(self):
        setup_db(self.db_file)
        db.connect()

    def close_db(self):
        db.close()

    def scan(self, music_dir):
        self.music_dir = os.path.abspath(music_dir)

        # Keep some stats
        self.total = 0
        self.not_changed = 0
        self.updated = 0
        self.added = 0
        self.error = 0

        self.open_db()
        self.traverse("")
        self.close_db()

        print("Checked %s tracks:" % self.total)
        print("  %5d tracks not changed since last run" % self.not_changed)
        print("  %5d tracks added" % self.added)
        print("  %5d tracks updated" % self.updated)
        print("  %5d tracks could not be read" % self.error)
        if self.total != self.not_changed + self.updated + self.added + self.error:
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

        query = "%s~%d %s~%d" % (self.encode_string(artist_name), distance, self.encode_string(recording_name), distance)
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


    def add_or_update_recording(self, mdata):

        with db.atomic() as transaction:
            try:
                recording = Recording.select().where(Recording.file_path == mdata['file_path']).get()
                recording.artist_name = mdata["artist_name"]
                recording.release_name = mdata["release_name"]
                recording.recording_name = mdata["recording_name"]
                recording.artist_mbid = mdata["artist_mbid"]
                recording.release_mbid = mdata["release_mbid"]
                recording.recording_mbid = mdata["recording_mbid"]
                recording.mtime = mdata["mtime"]
                recording.track_num = mdata["track_num"]
                recording.save()
                return "updated"
            except peewee.DoesNotExist:
                recording = Recording.create(file_path = mdata['file_path'],
                    artist_name = mdata["artist_name"],
                    release_name = mdata["release_name"],
                    name = mdata["recording_name"],
                    artist_mbid = mdata["artist_mbid"],
                    release_mbid = mdata["release_mbid"],
                    recording_mbid = mdata["recording_mbid"],
                    mtime = mdata["mtime"],
                    duration = mdata["duration"],
                    track_num = mdata["track_num"])
                return "added"


    def add_file(self, relative_path, format, mtime, update):
        file_path = os.path.join(self.music_dir, relative_path)

        # We've never seen this before, or it was updated since we last saw it.
        if format == "mp3":
            mdata = mp3.read(file_path)
        elif format == "flac":
            mdata = flac.read(file_path)
        elif format == "ogg":
            mdata = ogg_vorbis.read(file_path)
        elif format == "m4a":
            mdata = m4a.read(file_path)
        elif format == "wma":
            mdata = wma.read(file_path)

        # TODO: In the future we should attempt to read basic metadata from
        # the filename here. But, if you have untagged files, this tool
        # really isn't for you anyway. heh.
        if mdata is not None:
            mdata["mtime"] = mtime
            mdata["file_path"] = file_path

        # now add/update the record
        return self.add_or_update_recording(mdata)

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
            print("  unknown %s" % base)
            self.skipped += 1
            return

        exists = False
        try:
            recording = Recording.get(Recording.file_path == fullpath)
        except peewee.DoesNotExist as err:
            recording = None

        if recording:
            exists = True
            if recording.mtime == ts:
                self.not_changed += 1
                print("unchanged %s" % base)
                return

        # read the file's last modified time to avoid re-reading tags
        stats = os.stat(fullpath)
        ts = datetime.datetime.fromtimestamp(stats[8])

        status = self.add_file(relative_path, ext, ts, exists)
        if status == "updated":
            print("    update %s" % base)
            self.updated += 1
        elif status == "added":
            print("      add %s" % base)
            self.added += 1
        else:
            self.error += 1
            print("    error %s" % base)

    def database_cleanup(self):
        '''
        Look for missing tracks and remove them from the DB. Then look for empty releases/artists and remove those too
        '''

        self.open_db()
        query = Recording.select()
        for recording in query:
            if not os.path.exists(recording.file_path):
                print("DEL %s" % recording.file_path)
                recording.delete()
        self.close_db()
