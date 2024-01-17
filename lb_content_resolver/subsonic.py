import datetime
import os
import sys
from uuid import UUID

import libsonic
from tqdm import tqdm

from lb_content_resolver.database import Database
from lb_content_resolver.model.database import db
from lb_content_resolver.utils import bcolors


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

        self.run_sync()

        print("Checked %s albums:" % self.total)
        print("  %5d albums matched" % self.matched)
        print("  %5d albums with errors" % self.error)

    def run_sync(self):
        """
            Perform the sync between the local collection and the subsonic one.
        """

        print("[ connect to subsonic ]")

        import config
        conn = libsonic.Connection(config.SUBSONIC_HOST, config.SUBSONIC_USER, config.SUBSONIC_PASSWORD, config.SUBSONIC_PORT)
        cursor = db.connection().cursor()

        print("[ load albums ]")
        album_ids = set()
        albums = []
        offset = 0
        while True:
            results = conn.getAlbumList2(ltype="alphabeticalByArtist", size=self.BATCH_SIZE, offset=offset)
            albums.extend(results["albumList2"]["album"])
            album_ids.update([r["id"] for r in results["albumList2"]["album"] ])

            album_count = len(results["albumList2"]["album"])
            offset += album_count
            if album_count < self.BATCH_SIZE:
                break

        print("[ loaded %d albums ]" % len(album_ids))

        pbar = tqdm(total=len(album_ids))
        recordings = []

        for album in albums:
            album_info = conn.getAlbum(id=album["id"])

            # Some servers might already include the MBID in the list or album response
            album_mbid = album_info.get("musicBrainzId", album.get("musicBrainzId"))
            if not album_mbid:
                album_info2 = conn.getAlbumInfo2(id=album["id"])
                try:
                    album_mbid = album_info2["albumInfo"]["musicBrainzId"]
                except KeyError:
                    pbar.write(bcolors.FAIL + "FAIL " + bcolors.ENDC + "subsonic album '%s' by '%s' has no MBID" %
                            (album["name"], album["artist"]))
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
                           (album["name"][:49], album["artist"][:49]))
                self.matched += 1
            else:
                pbar.write(bcolors.FAIL + "FAIL " + bcolors.ENDC + "album %-50s %-50s" %
                           (album["name"][:49], album["artist"][:49]))
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

        recording_index = { r[0]:r[1] for r in recordings }

        cursor = db.connection().cursor()
        with db.atomic() as transaction:

            placeholders = ",".join(("?", ) * len(recording_index))
            cursor.execute("""SELECT recording_id
                                FROM recording_subsonic
                               WHERE recording_id in (%s)""" % placeholders, tuple(recording_index.keys()))
            existing_ids = { row[0]:None for row in cursor.fetchall() }
            existing_recordings = []
            new_recordings = []
            for r in recordings:
                if r[0] in existing_ids:
                    existing_recordings.append((r[0], r[1], datetime.datetime.now(), r[0]))
                else:
                    new_recordings.append((r[0], r[1], datetime.datetime.now()))

            cursor.executemany("""INSERT INTO recording_subsonic (recording_id, subsonic_id, last_updated)
                                       VALUES (?, ?, ?)""", tuple(new_recordings))

            cursor.executemany("""UPDATE recording_subsonic
                                     SET recording_id = ?
                                       , subsonic_id = ?
                                       , last_updated = ?
                                   WHERE recording_id = ?""", tuple(existing_recordings))


        # This concise query does the same as above. But older versions of python/sqlite on Raspberry Pis 
        # don't support upserts yet. :(
        #recordings = [(r[0], r[1], datetime.datetime.now()) for r in recordings]
        #cursor.executemany(
        #    """INSERT INTO recording_subsonic (recording_id, subsonic_id, last_updated)
        #                            VALUES (?, ?, ?)
        #         ON CONFLICT DO UPDATE SET recording_id = excluded.recording_id
        #                                 , subsonic_id = excluded.subsonic_id
        #                                 , last_updated = excluded.last_updated""", recordings)



    def upload_playlist(self, jspf):
        """
            Given a JSPF playlist, upload the playlist to the subsonic API.
        """

        import config
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
