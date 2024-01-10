from abc import abstractmethod
from collections import namedtuple
import os
import datetime
from pathlib import Path
import sys
from time import time
from uuid import UUID

from unidecode import unidecode
import peewee
from tqdm import tqdm

from lb_content_resolver.model.database import db, setup_db
from lb_content_resolver.model.recording import Recording, RecordingMetadata
from lb_content_resolver.model.unresolved_recording import UnresolvedRecording
from lb_content_resolver.model.subsonic import RecordingSubsonic
from lb_content_resolver.model.tag import Tag, RecordingTag
from lb_content_resolver.formats import mp3, m4a, flac, ogg_opus, ogg_vorbis, wma

SupportedFormat = namedtuple('SupportedFormat', ('extensions', 'handler'))
SUPPORTED_FORMATS = (
    SupportedFormat({'.flac'}, flac),
    SupportedFormat({'.ogg'}, ogg_vorbis),
    SupportedFormat({'.opus'}, ogg_opus),
    SupportedFormat({'.mp3', '.mp2', '.m2a'}, mp3),
    SupportedFormat({'.m4a', '.m4b', '.m4p', '.m4v', '.m4r', '.mp4'}, m4a),
    SupportedFormat({'.wma'}, wma),
)

ALL_EXTENSIONS = set()
EXTENSION_HANDLER = dict()
for fmt in SUPPORTED_FORMATS:
    ALL_EXTENSIONS.update(fmt.extensions)
    for ext in fmt.extensions:
        EXTENSION_HANDLER[ext] = fmt.handler


def match_extensions(filepath, extensions):
    return Path(filepath).suffix.lower() in extensions


class Database:
    ''' 
    Keep a database with metadata for a collection of local music files.
    '''
    def __init__(self, db_file):
        self.db_file = db_file
        self.fuzzy_index = None

    def create(self):
        """ 
            Create the database. Can be run again to create tables that have been recently added to the code,
            but don't exist in the DB yet.
        """

        setup_db(self.db_file)
        db.connect()
        db.create_tables([Recording, RecordingMetadata, Tag, RecordingTag, RecordingSubsonic, UnresolvedRecording])

    def open(self):
        """ 
            Open the database file and connect to the db.
        """
        try:
            setup_db(self.db_file)
            db.connect()
        except peewee.OperationalError:
            print("Cannot open database index file: '%s'" % self.db_file)
            sys.exit(-1)

    def close(self):
        """ Close the db."""
        db.close()

    def scan(self, music_dir):
        """
            Scan a music dir and add tracks to sqlite.
        """
        self.music_dir = os.path.abspath(music_dir)

        # Keep some stats
        self.total = 0
        self.not_changed = 0
        self.updated = 0
        self.added = 0
        self.error = 0
        self.skipped = 0

        # Future improvement, commit to DB only every 1000 tracks or so.
        print("Check collection size...")
        self.track_count_estimate = 0
        self.traverse("", dry_run=True)
        self.audio_file_count = self.track_count_estimate
        print("Found %s audio files" % self.audio_file_count)

        with tqdm(total=self.track_count_estimate) as self.progress_bar:
            self.traverse("")

        self.close()

        print("Checked %s tracks:" % self.total)
        print("  %5d tracks not changed since last run" % self.not_changed)
        print("  %5d tracks added" % self.added)
        print("  %5d tracks updated" % self.updated)
        print("  %5d tracks could not be read" % self.error)
        if self.total != self.not_changed + self.updated + self.added + self.error:
            print("And for some reason these numbers don't add up to the total number of tracks. Hmmm.")

    def traverse(self, relative_path, dry_run=False):
        """
            This recursive function searches for audio files and descends into sub directories 
        """

        if not relative_path:
            fullpath = self.music_dir
        else:
            fullpath = os.path.join(self.music_dir, relative_path)

        for f in sorted(os.listdir(fullpath)):
            if f in {'.', '..'}:
                continue

            new_relative_path = os.path.join(relative_path, f)
            new_full_path = os.path.join(self.music_dir, new_relative_path)
            if os.path.isfile(new_full_path) and match_extensions(new_full_path, ALL_EXTENSIONS):
                if not dry_run:
                    self.add(new_relative_path)
                else:
                    self.track_count_estimate += 1
            elif os.path.isdir(new_full_path):
                if not self.traverse(new_relative_path, dry_run):
                    return False

        return True

    def add_or_update_recording(self, mdata):
        """ 
            Given a Recording, add it to the DB if it does not exist. If it does,
            update the recording instead
        """

        with db.atomic() as transaction:
            if mdata is not None:
                details = " %d%% " % (100 * self.total / self.audio_file_count)
                details += " %-30s %-30s %-30s" % ((mdata.get("recording_name", "") or "")[:29], 
                                                   (mdata.get("release_name", "") or "")[:29],
                                                   (mdata.get("artist_name", "") or "")[:29])
            else:
                details = ""

            try:
                recording = Recording.select().where(Recording.file_path == mdata['file_path']).get()
            except:
                recording = Recording.create(file_path=mdata['file_path'],
                                             artist_name=mdata["artist_name"],
                                             release_name=mdata["release_name"],
                                             recording_name=mdata["recording_name"],
                                             artist_mbid=mdata["artist_mbid"],
                                             release_mbid=mdata["release_mbid"],
                                             recording_mbid=mdata["recording_mbid"],
                                             mtime=mdata["mtime"],
                                             duration=mdata["duration"],
                                             track_num=mdata["track_num"],
                                             disc_num=mdata["disc_num"])
                return "added", details

            recording.artist_name = mdata["artist_name"]
            recording.release_name = mdata["release_name"]
            recording.recording_name = mdata["recording_name"]
            recording.artist_mbid = mdata["artist_mbid"]
            recording.release_mbid = mdata["release_mbid"]
            recording.recording_mbid = mdata["recording_mbid"]
            recording.mtime = mdata["mtime"]
            recording.track_num = mdata["track_num"]
            recording.disc_num = mdata["disc_num"]
            recording.save()
            return "updated", details

    def read_metadata_and_add(self, relative_path, extension, mtime, update):
        """
            Read the metadata from supported files and then add the 
            recording to the DB.
        """

        file_path = os.path.join(self.music_dir, relative_path)

        # We've never seen this before, or it was updated since we last saw it.
        mdata = EXTENSION_HANDLER[extension].read(file_path)

        # In the future we should attempt to read basic metadata from
        # the filename here. But, if you have untagged files, this tool
        # really isn't for you anyway. heh.
        if mdata is not None:
            mdata["mtime"] = mtime
            mdata["file_path"] = file_path

            mdata["artist_mbid"] = self.convert_to_uuid(mdata["artist_mbid"])
            mdata["release_mbid"] = self.convert_to_uuid(mdata["release_mbid"])
            mdata["recording_mbid"] = self.convert_to_uuid(mdata["recording_mbid"])

            # now add/update the record
            return self.add_or_update_recording(mdata)

        return "error", "Failed to read metadata from audio file."

    def convert_to_uuid(self, value):
        """
            Convert the given string to a UUID or return None if not a valid UUID.
        """

        if value is not None:
            try:
                return UUID(value)
            except ValueError:
                return None
        return None

    def add(self, relative_path):
        """
            Given a file, check to see if we already have it and if we do,
            if it has changed since the last time we read it. If it is new
            or has been changed, update in the DB.
        """

        fullpath = os.path.join(self.music_dir, relative_path)

        # update the progress bar
        self.progress_bar.update(1)

        base, ext = os.path.splitext(relative_path)
        base = os.path.basename(relative_path)

        if not match_extensions(relative_path, ALL_EXTENSIONS):
            print("  unknown %s" % base)
            self.skipped += 1
            return

        self.total += 1

        exists = False
        try:
            recording = Recording.get(Recording.file_path == fullpath)
        except peewee.DoesNotExist as err:
            recording = None

        # Check to see if the file in question has changed since the last time
        # we looked at it. If not, skip it for speed
        stats = os.stat(fullpath)
        ts = datetime.datetime.fromtimestamp(stats[8])

        if recording:
            exists = True
            if recording.mtime == ts:
                self.not_changed += 1
                self.progress_bar.write("unchanged %s" % base)
                return

        status, details = self.read_metadata_and_add(relative_path, ext, ts, exists)
        if status == "updated":
            self.progress_bar.write("   update %s" % details)
            self.updated += 1
        elif status == "added":
            self.progress_bar.write("      add %s" % details)
            self.added += 1
        else:
            self.error += 1
            self.progress_bar.write("    error %s" % details)


    def database_cleanup(self, dry_run):
        '''
        Look for missing tracks and remove them from the DB. Then look for empty releases/artists and remove those too
        '''

        query = Recording.select()
        recording_ids = []
        for recording in query:
            if not os.path.exists(recording.file_path):
                print("RM %s" % recording.file_path)
                recording_ids.append(recording.id)

        if not recording_ids:
            print("No cleanup needed, all recordings found")
            return

        if not dry_run:
            placeholders = ",".join(("?", ) * len(recording_ids))
            db.execute_sql("""DELETE FROM recording WHERE recording.id IN (%s)""" % placeholders, tuple(recording_ids))
            print("Stale references removed")
        else:
            print("--delete not specified, no refences removed")

    def metadata_sanity_check(self, include_subsonic=False):
        """
        Run a sanity check on the DB to see if data is missing that is required for LB Radio to work.
        """

        num_recordings = db.execute_sql("SELECT COUNT(*) FROM recording").fetchone()[0]
        num_metadata = db.execute_sql("SELECT COUNT(*) FROM recording_metadata").fetchone()[0]
        num_subsonic = db.execute_sql("SELECT COUNT(*) FROM recording_subsonic").fetchone()[0]

        if num_metadata == 0:
            print("sanity check: You have not downloaded metadata for your collection. Run the metadata command.")
        elif num_metadata < num_recordings // 2:
            print("sanity check: Only %d of your %d recordings have metadata information available. Run the metdata command." %
                  (num_metadata, num_recordings))

        if include_subsonic:
            if num_subsonic == 0 and include_subsonic:
                print(
                    "sanity check: You have not matched your collection against the collection in subsonic. Run the subsonic command.")
            elif num_subsonic < num_recordings // 2:
                print("sanity check: Only %d of your %d recordings have subsonic matches. Run the subsonic command." %
                      (num_subsonic, num_recordings))
