import os
from uuid import UUID

import libsonic

from lb_content_resolver.database import Database
from lb_content_resolver.model.database import db
import config


class SubsonicDatabase(Database):
    ''' 
    Add subsonic sync capabilities to the Database
    '''

    MAX_ALBUMS_PER_CALL = 3  # 500

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

        cursor = db.connection().cursor()

        from icecream import ic
        print("Fetch recordings")
        album_count = 0
        while True: 
            recordings = []
            albums_this_batch = 0;
            albums = conn.getAlbumList(ltype="alphabeticalByArtist", size=self.MAX_ALBUMS_PER_CALL, offset=album_count)

            for album in albums["albumList"]["album"]:
                album_info = conn.getAlbumInfo2(id=album["id"])
                album_mbid = album_info["albumInfo"]["musicBrainzId"]

                cursor.execute("""SELECT recording.id
                                       , track_num
                                    FROM recording
                                   WHERE release_mbid = ?""", (album_mbid,))
                release_tracks = { row[1]:row[0] for row in cursor.fetchall() }

                album_info = conn.getAlbum(id=album["id"])
                for song in album_info["album"]["song"]:
                    recordings.append((song["id"], song["track"], song["discNumber"], release_tracks[song["track"]]))

                ic(recordings)
                return

                album_count += 1
                albums_this_batch += 1

            self.process_recordings(recordings)

            print("fetched %d releases" % albums_this_batch)
            if albums_this_batch < self.MAX_ALBUMS_PER_CALL:
                break

    def process_recordings(self, recordings):
        album_mbids = tuple(recordings.keys()) 
        placeholders = ",".join([ "?" for i in range(len(paths)) ])

        cursor = db.connection().cursor()
        cursor.execute("""SELECT recording_id
                               , subsonic_id
                               , file_path
                            FROM recording_subsonic
                            JOIN recording
                              ON recording.id = recording_subsonic.recording_id
                           WHERE recording.file_path IN (%s)""" % placeholders, paths)

        to_save = []
        for row in cursor.fetchall():
            print(row)
            recording_id, subsonic_id, file_path = row
            new_subsonic_id = recordings[file_path]
            if new_subsonic_id != subsonic_id:
                to_save.append((recording_id, subsonic_id, file_path))

        print("Save:")
        print(to_save)

