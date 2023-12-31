import datetime
import os
import sys
from uuid import UUID

import libsonic
from tqdm import tqdm

from lb_content_resolver.database import Database
from lb_content_resolver.model.database import db
from lb_content_resolver.utils import bcolors
import config


class SubsonicDatabase(Database):
    ''' 
    Add subsonic sync capabilities to the Database
    '''
    
    # Determined by the number of albums we can fetch in one go
    BATCH_SIZE = 500

    def __init__(self, index_dir):
        Database.__init__(self, index_dir)

    def sync(self):
        """
            Scan the subsonic client specified in config.py
        """

        # Keep some stats
        self.total = 0
        self.matched = 0
        self.error = 0

        self.open_db()
        self.run_sync()
        self.close_db()

        print("Checked %s albums:" % self.total)
        print("  %5d albums matched" % self.matched)
        print("  %5d albums with errors" % self.error)

    def run_sync(self):
        """
            Perform the sync between the local collection and the subsonic one.
        """

        print("[ connect to subsonic ]")
        conn = libsonic.Connection(config.SUBSONIC_HOST, config.SUBSONIC_USER, config.SUBSONIC_PASSWORD, config.SUBSONIC_PORT)
        cursor = db.connection().cursor()

        print("[ load albums ]")
        album_ids = set()
        albums = []
        offset = 0
        while True:
            results = conn.getAlbumList(ltype="alphabeticalByArtist", size=self.BATCH_SIZE, offset=offset)
            albums.extend(results["albumList"]["album"])
            album_ids.update([r["id"] for r in results["albumList"]["album"] ])

            album_count = len(results["albumList"]["album"])
            offset += album_count
            if album_count < self.BATCH_SIZE:
                break

        print("[ loaded %d albums ]" % len(album_ids))

        pbar = tqdm(total=len(album_ids))
        recordings = []

        for album in albums:
            album_info = conn.getAlbumInfo2(id=album["id"])
            try:
                album_mbid = album_info["albumInfo"]["musicBrainzId"]
            except KeyError:
                pbar.write(bcolors.FAIL + "FAIL " + bcolors.ENDC + "subsonic album '%s' by '%s' has no MBID" %
                           (album["album"], album["artist"]))
                self.error += 1
                continue

            cursor.execute(
                """SELECT recording.id
                                   , track_num
                                   , COALESCE(disc_num, 1)
                                FROM recording
                               WHERE release_mbid = ?""", (album_mbid, ))

            # create index on (track_num, disc_num)
            release_tracks = {(row[1], row[2]): row[0] for row in cursor.fetchall()}

            album_info = conn.getAlbum(id=album["id"])

            if len(release_tracks) == 0:
                pbar.write("For album %s" % album_mbid)
                pbar.write("loaded %d of %d expected tracks from DB." %
                           (len(release_tracks), len(album_info["album"].get("song", []))))

            msg = ""
            if "song" not in album_info["album"]:
                msg += "   No songs returned\n"
            else:
                for song in album_info["album"]["song"]:
                    if (song["track"], song.get("discNumber", 1)) in release_tracks:
                        recordings.append((release_tracks[(song["track"], song["discNumber"])], song["id"]))
                    else:
                        msg += "   Song not matched: '%s'\n" % song["title"]
                        continue
            if msg == "":
                pbar.write(bcolors.OKGREEN + "OK   " + bcolors.ENDC + "album %-50s %-50s" %
                           (album["album"][:49], album["artist"][:49]))
                self.matched += 1
            else:
                pbar.write(bcolors.FAIL + "FAIL " + bcolors.ENDC + "album %-50s %-50s" %
                           (album["album"][:49], album["artist"][:49]))
                pbar.write(msg)
                self.error += 1

            if len(recordings) >= self.BATCH_SIZE:
                self.update_recordings(recordings)
                recordings = []

            self.total += 1
            pbar.update(1)

        if len(recordings) >= self.BATCH_SIZE:
            self.update_recordings(recordings)


    def update_recordings(self, recordings):
        """
            Given a list of recording_subsonic records, update the DB.
            Updates recording_id, subsonic_id, last_update
        """

        recordings = [(r[0], r[1], datetime.datetime.now()) for r in recordings]

        cursor = db.connection().cursor()
        with db.atomic() as transaction:
            cursor.executemany(
                """INSERT INTO recording_subsonic (recording_id, subsonic_id, last_updated)
                                        VALUES (?, ?, ?)
                     ON CONFLICT DO UPDATE SET recording_id = excluded.recording_id
                                             , subsonic_id = excluded.subsonic_id
                                             , last_updated = excluded.last_updated""", recordings)

    def upload_playlist(self, jspf):
        """
            Given a JSPF playlist, upload the playlist to the subsonic API.
        """

        conn = libsonic.Connection(config.SUBSONIC_HOST, config.SUBSONIC_USER, config.SUBSONIC_PASSWORD, config.SUBSONIC_PORT)

        song_ids = []
        for track in jspf["playlist"]["track"]:
            try:
                song_ids.append(
                    track["extension"]["https://musicbrainz.org/doc/jspf#track"]["additional_metadata"]["subsonic_identifier"][33:])
            except KeyError:
                continue

        name = jspf["playlist"]["title"]
        conn.createPlaylist(name=name, songIds=song_ids)
