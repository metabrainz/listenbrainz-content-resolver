import os

import libsonic

from lb_content_resolver.database import Database
from lb_content_resolver.model.database import db
import config


class SubsonicDatabase(Database):
    ''' 
    Add subsonic sync capabilities to the Database
    '''

    MAX_ALBUMS_PER_CALL = 10  # 500

    def __init__(self, index_dir):
        Database.__init__(self, index_dir)

    def sync(self):
        """
            Scan the subsonic client specified in config.py
        """

        # Keep some stats
        self.total = 0
        self.added = 0
        self.removed = 0
        self.updated = 0

        self.open_db()
        self.run_sync()
        self.close_db()

        print("Checked %s tracks:" % self.total)
        print("  %5d tracks added" % self.added)
        print("  %5d tracks updated" % self.updated)
        print("  %5d tracks removed" % self.removed)

    def run_sync(self):

        print("Connect to subsonic..")
        conn = libsonic.Connection(config.SUBSONIC_HOST, config.SUBSONIC_USER, config.SUBSONIC_PASSWORD, config.SUBSONIC_PORT)

        print("Fetch recordings")
        album_count = 0
        while True: 
            recordings = {}
            albums_this_batch = 0;
            albums = conn.getAlbumList(ltype="alphabeticalByArtist", size=self.MAX_ALBUMS_PER_CALL, offset=album_count)

            for album in albums["albumList"]["album"]:
                album_info = conn.getAlbum(id=album["id"])
                for song in album_info["album"]["song"]:
                    recordings[song["path"]] = song["id"]
                album_count += 1
                albums_this_batch += 1

            self.process_recordings(recordings)

            print("fetched %d releases" % albums_this_batch)
            if albums_this_batch < self.MAX_ALBUMS_PER_CALL:
                break

    def process_recordings(self, recordings):
        paths = tuple(recordings.keys()) 
        placeholders = ",".join([ "?" for i in range(len(paths)) ])

        cursor = db.connection().cursor()
        cursor.execute("""SELECT recording_id
                               , subsonic_id
                            FROM recording_subsonic
                            JOIN recording
                              ON recording.id = recording_subsonic.recording_id
                           WHERE recording.file_path IN (%s)""" % placeholders, paths)
        for row in cursor.fetchall():
            print(row)
