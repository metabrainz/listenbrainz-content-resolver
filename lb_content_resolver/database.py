from abc import abstractmethod
from collections import namedtuple
from enum import IntEnum
import os
import datetime
from mutagen import MutagenError
from pathlib import Path
import sys
from time import time
from types import SimpleNamespace
from uuid import UUID

from unidecode import unidecode
import peewee
from tqdm import tqdm

from lb_content_resolver.model.database import db, setup_db
from lb_content_resolver.model.recording import Recording, RecordingMetadata
from lb_content_resolver.model.unresolved_recording import UnresolvedRecording
from lb_content_resolver.model.subsonic import RecordingSubsonic
from lb_content_resolver.model.tag import Tag, RecordingTag
from lb_content_resolver.model.directory import Directory
from lb_content_resolver.formats import mp3, m4a, flac, ogg_opus, ogg_vorbis, wma

from lb_content_resolver.utils import existing_dirs


SUPPORTED_FORMATS = (
    flac,
    m4a,
    mp3,
    ogg_opus,
    ogg_vorbis,
    wma,
)

ALL_EXTENSIONS = set()
EXTENSION_HANDLER = dict()
for fmt in SUPPORTED_FORMATS:
    ALL_EXTENSIONS.update(fmt.EXTENSIONS)
    for ext in fmt.EXTENSIONS:
        EXTENSION_HANDLER[ext] = fmt


class Status(IntEnum):
    NOCHANGE = 0
    ADD = 1
    UPDATE = 2
    ERROR = 255


STATUSMSG = {
    Status.NOCHANGE: '',
    Status.ADD: 'add',
    Status.UPDATE: 'update',
    Status.ERROR: 'error',
}

StatusDetails = namedtuple('StatusDetails', ('recording_name', 'artist_name', 'release_name'))
StatusData = namedtuple('StatusData', ('status', 'filenumber', 'details'))


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
        try:
            db_dir = os.path.dirname(os.path.realpath(self.db_file))
            os.makedirs(db_dir, exist_ok=True)
            setup_db(self.db_file)
            db.connect()
            db.create_tables(
                (
                    Recording,
                    RecordingMetadata,
                    Tag,
                    RecordingTag,
                    RecordingSubsonic,
                    UnresolvedRecording,
                    Directory,
                )
            )
        except Exception as e:
            print("Failed to create db file %r: %s" % (self.db_file, e))

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

    def scan(self, music_dirs, chunksize=100):
        """
            Scan music directories and add tracks to sqlite.
        """
        if not music_dirs:
            print("No directory to scan")
            return

        self.music_dirs = tuple(sorted(set(existing_dirs(music_dirs))))
        if not self.music_dirs:
            print("No valid directories to scan")
            return

        self.chunksize = chunksize

        # Keep some stats
        self.total = 0
        self.statuscounters = {s: 0 for s in Status}
        self.file_count = 0
        self.audio_file_count = 0
        self.dirs_count = 0
        self.skip_dirs = set()

        # Future improvement, commit to DB only every 1000 tracks or so.
        print("Check collection size...")
        print("Counting candidates in %s ..." % ", ".join(self.music_dirs))
        self.traverse(dry_run=True)
        print("Found %s audio file(s) among %s file(s) in %s directorie(s) (%d skipped)"
              % (self.audio_file_count, self.file_count, self.dirs_count, len(self.skip_dirs)))

        with tqdm(total=self.audio_file_count) as self.progress_bar:
            print("Scanning ...")
            self.traverse()

        self.close()

        print("Checked %s tracks:" % self.total)
        print("  %5d tracks not changed since last run" % self.statuscounters[Status.NOCHANGE])
        print("  %5d tracks added" % self.statuscounters[Status.ADD])
        print("  %5d tracks updated" % self.statuscounters[Status.UPDATE])
        print("  %5d tracks could not be read" % self.statuscounters[Status.ERROR])
        if self.total != sum(self.statuscounters.values()):
            print("And for some reason these numbers don't add up to the total number of tracks. Hmmm.")

    def traverse(self, dry_run=False):
        """
            This function searches for audio files and descends into sub directories
        """
        seen = set()
        if dry_run:
            self.dirs_count = 0
            self.audio_file_count = 0
        filenumber = 0
        self.chunk = dict()

        for topdir in self.music_dirs:
            if dry_run:
                self.dirs_count += 1

            for root, dirs, files in os.walk(topdir):
                root = os.path.realpath(root)

                if dry_run:
                    self.dirs_count += len(dirs)
                    if not self.dir_has_changed(root):
                        self.skip_dirs.add(root)

                if root in self.skip_dirs:
                    continue

                for name in files:
                    file_path = os.path.realpath(os.path.join(root, name))
                    if file_path in seen:
                        continue
                    seen.add(file_path)
                    if os.path.isfile(file_path) and match_extensions(file_path, ALL_EXTENSIONS):
                        filenumber += 1
                        if not dry_run:
                            self.add(file_path, filenumber)
                            if filenumber % self.chunksize == 0:
                                self.process_chunk()

        if not dry_run:
            self.process_chunk()
        else:
            self.file_count = len(seen)
            self.audio_file_count = filenumber

    def dir_has_changed(self, dir_path):
        try:
            stats = os.stat(dir_path)
            mtime = datetime.datetime.fromtimestamp(stats[8])
            directory = Directory.get_or_none(Directory.dir_path == dir_path)
            has_changed = directory is None or directory.mtime != mtime
            if has_changed:
                Directory.insert(dir_path=dir_path, mtime=mtime).on_conflict_replace().execute()
                return True
        except Exception as e:
            print("Can't stat dir %r: %s" % (dir_path, e))
        return False

    def read_metadata(self, file_path, mtime):
        """
            Read metadata from audio file
            On error, returns None, error msg
            On success, returns metadata dict, StatusDetails
        """
        data = None
        try:
            base, extension = os.path.splitext(file_path)
            handler = EXTENSION_HANDLER[extension]
            tags = handler.READER(file_path)
            mdata = handler.get_metadata(tags)
            if mdata is not None:
                data = {
                    "artist_mbid": self.convert_to_uuid(mdata["artist_mbid"]),
                    "artist_name": mdata["artist_name"],
                    "disc_num": mdata["disc_num"],
                    "file_path": file_path,
                    "mtime": mtime,
                    "recording_mbid": self.convert_to_uuid(mdata["recording_mbid"]),
                    "recording_name": mdata["recording_name"],
                    "release_mbid": self.convert_to_uuid(mdata["release_mbid"]),
                    "release_name": mdata["release_name"],
                    "track_num": mdata["track_num"],
                }
                details = StatusDetails(
                    recording_name=data['recording_name'],
                    artist_name=data['artist_name'],
                    release_name=data['release_name'],
                )
                return data, details
            else:
                return None, "Not enough metadata from file %r" % file_path
        except MutagenError as e:
            return None, "Cannot read metadata from file %r: %s" % (file_path, e)
        except Exception as e:
            return None, "Failed to read audio file %r: %s" % (file_path, e)

    def iterate_chunk(self, chunk):
        """
            For all items in the chunk, read metadata and yield resulting data (or None),
            and matching details (status, filenumber, and details (or error string))
        """
        for file_path, chunkitemdata in chunk.items():
            data, details = self.read_metadata(file_path, chunkitemdata.mtime)
            if data is not None:
                status = Status.UPDATE if chunkitemdata.is_update else Status.ADD
            else:
                status = Status.ERROR

            yield data, StatusData(status, chunkitemdata.filenumber, details)

    def read_metadata_and_add(self, chunk):
        """
            Read the metadata from supported files and then add the
            recording to the DB.
        """
        statuses = list()
        datas = list()

        for data, statusdata in self.iterate_chunk(chunk):
            statuses.append(statusdata)
            if data is not None:
                datas.append(data)

        if datas:
            with db.atomic() as transaction:
                result = Recording.insert_many(datas).on_conflict_replace().execute()

        return statuses

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

    def fmtdetails(self, statusdata):
        """
            Format progress message
        """
        s = "%-8s %5.1f%% " % (STATUSMSG[statusdata.status], 100 * statusdata.filenumber / self.audio_file_count)
        try:
            s += " %-30s %-30s %-30s" % (
                (statusdata.details.recording_name or "")[:29],
                (statusdata.details.artist_name or "")[:29],
                (statusdata.details.release_name or "")[:29],
            )
        except:
            # details can be a string
            s += str(statusdata.details)
        return s

    def update_status(self, statusdata):
        """
            Update status counter and display matching progress
        """
        self.statuscounters[statusdata.status] += 1
        self.progress_bar.write(self.fmtdetails(statusdata))

    def add(self, file_path, audio_file_count):
        """
            Given a file, check to see if we already have it and if we do,
            if it has changed since the last time we read it. If it is new
            or has been changed, update in the DB.
        """

        # update the progress bar
        self.progress_bar.update(1)

        self.total += 1

        # Check to see if the file in question has changed since the last time
        # we looked at it.
        try:
            stats = os.stat(file_path)
            mtime = datetime.datetime.fromtimestamp(stats[8])
            chunkitemdata = SimpleNamespace(mtime=mtime, filenumber=audio_file_count, is_update=False)
            self.chunk[file_path] = chunkitemdata
        except Exception as e:
            details = "Can't stat file %r: %s" % (file_path, e)
            statusdata = StatusData(Status.ERROR, audio_file_count, details)
            self.update_status(statusdata)

    def process_chunk(self):
        """
            Process current chunk
        """
        statuses = list()

        # find existing recordings and compare modification time
        for recording in Recording.select().where(Recording.file_path.in_(tuple(self.chunk))):
            if recording.mtime == self.chunk[recording.file_path].mtime:
                # file didn't change since last time, skip it
                statusdata = StatusData(
                    Status.NOCHANGE,
                    self.chunk[recording.file_path].filenumber,
                    StatusDetails(
                        recording_name=recording.recording_name,
                        artist_name=recording.artist_name,
                        release_name=recording.release_name,
                    )
                )
                statuses.append(statusdata)
                # unchanged files are deleted from chunk
                del self.chunk[recording.file_path]
            else:
                #  mark existing data for update
                self.chunk[recording.file_path].is_update = True

        if self.chunk:
            # add or update metadata for remaining files in the chunk
            statuses += self.read_metadata_and_add(self.chunk)
            # reset chunk
            self.chunk = dict()

        for statusdata in sorted(statuses, key=lambda s: s.filenumber):
            self.update_status(statusdata)

    def database_cleanup(self, dry_run):
        """
        Look for missing files and directory entries and remove them from the DB.
        """
        PathId = namedtuple('PathId', ('path', 'id'))

        recordings = tuple(
            PathId(r.file_path, r.id)
            for r in Recording.select(Recording.file_path, Recording.id)
            if not os.path.isfile(r.file_path)
        )
        directories = tuple(
            PathId(d.dir_path, d.id)
            for d in Directory.select(Directory.dir_path, Directory.id)
            if not os.path.isdir(d.dir_path)
        )

        if not recordings and not directories:
            print("No cleanup needed.")
            return

        for elem in sorted(recordings + directories):
            print("RM %s" % elem.path)

        print("%d recordings and %d directory entries to remove from database" % (len(recordings), len(directories)))
        if not dry_run:
            with db.atomic() as txn:
                ids = tuple(r.id for r in recordings)
                query = Recording.delete().where(Recording.id.in_(ids))
                count = query.execute()
                print("%d recordings removed" % count)
                ids = tuple(d.id for d in directories)
                query = Directory.delete().where(Directory.id.in_(ids))
                count = query.execute()
                print("%d directory entries removed" % count)
            print("Vacuuming database...")
            db.execute_sql('VACUUM')
            print("Done.")
        else:
            print("Use command cleanup --remove to actually remove those.")

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
