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

# TODO: TEST FS scan


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
        print("  %5d recordings with errors" % self.error)

    def run_sync(self):
        """
            Perform the sync between the local collection and the subsonic one.
        """

        from icecream import ic
        print("[ connect to subsonic ]")
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

        # cross reference subsonic artist id to artitst_mbid
        artist_id_index = {}

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


            recordings = []
            for song in album_info["album"]["song"]:
                album = album_info["album"]
            
                if "artistId" in song:
                    artist_id = song["artistId"]
                else:
                    artist_id = album["artistId"]

                if artist_id not in artist_id_index:
                    artist = conn.getArtistInfo2(artist_id)
                    try:
                        artist_id_index[artist_id] = artist["artistInfo2"]["musicBrainzId"]
                    except KeyError:
                        pbar.write(bcolors.FAIL + "FAIL " + bcolors.ENDC + "recording '%s' by '%s' has no artist MBID" %
                                (album["name"], album["artist"]))
                        pbar.write("Consider retagging this file with Picard! ( https://picard.musicbrainz.org )")
                        self.error += 1
                        continue


#                if "musicBrainzId" not in song:
#                    song_details = conn.getSong(song["id"])
#                    ic(song_details)

                self.add_or_update_recording({
                    "artist_name": song["artist"],
                    "release_name": song["album"],
                    "recording_name": song["title"],
                    "artist_mbid": artist_id_index[artist_id],
                    "release_mbid": album_mbid,
                    "recording_mbid": "",
                    "duration": song["duration"] * 1000,
                    "track_num": song["track"],
                    "disc_num": song["discNumber"],
                    "subsonic_id": song["id"],
                    "file_path": "",
                    "mtime": datetime.datetime.now()
                    })

            pbar.write(bcolors.OKGREEN + "OK   " + bcolors.ENDC + "album %-50s %-50s" %
                       (album["name"][:49], album["artist"][:49]))
            self.matched += 1
            self.total += 1
            pbar.update(1)


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
