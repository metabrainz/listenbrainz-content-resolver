import os

import libsonic

from lb_content_resolver.database import Database
import config


class SubsonicDatabase(Database):
    ''' 
    Keep a database with metadata for a collection of files via a subsonic API
    '''

    MAX_ALBUMS_PER_CALL = 10  # 500

    def __init__(self, index_dir):
        super(SubsonicDatabase, self).__init__(index_dir)

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
                from icecream import ic
                album_info = conn.getAlbum(id=album["id"])
                ic(album_info)
                return
                for song in album_info["album"]["song"]:
                    recordings[song["id"]] = song["path"]
                album_count += 1
                albums_this_batch += 1

            self.process_recordings(recordings)

            print("fetched %d releases" % albums_this_batch)
            if albums_this_batch < self.MAX_ALBUMS_PER_CALL:
                break

    def process_recorings(self, recordings):
        pass

