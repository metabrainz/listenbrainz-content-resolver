import os
import datetime
import sys
from uuid import UUID

import peewee

from lb_content_resolver.model.database import db, setup_db
from lb_content_resolver.model.recording import Recording
from lb_content_resolver.fuzzy_index import FuzzyIndex
from lb_matching_tools.cleaner import MetadataCleaner
from lb_content_resolver.playlist import read_jspf_playlist, write_m3u_playlist

SUPPORTED_FORMATS = ["flac", "ogg", "mp3", "m4a", "wma"]


class ContentResolver:
    ''' 
    Scan a given path and enter/update the metadata in the search index
    '''

    def __init__(self, db):
        self.db = db
        self.fuzzy_index = None

    def build_index(self):
        """
            Fetch the data from the DB and then build the fuzzy lookup index.
        """

        artist_recording_data = self.db.get_artist_recording_metadata()
        for recording in Recording.select():
            artist_recording_data.append((recording.artist_name, recording.recording_name, recording.id))

        self.fuzzy_index = FuzzyIndex(self.db.index_dir)
        self.fuzzy_index.build(artist_recording_data)

    def resolve_recordings(self, query_data, match_threshold):
        """
        Given a list of dicts with artist_name and recording_name in query data and a matching threshold,
        attempt to match recordings by looking them up in the fuzzy index.
        """

        resolved_recordings = []

        # Set indexes in the data so we can correlate matches
        for i, data in enumerate(query_data):
            data["index"] = i

        mc = MetadataCleaner()
        while True:
            next_query_data = []
            hits = self.fuzzy_index.search(query_data)
            for hit, data in zip(hits, query_data):
                if hit["confidence"] < match_threshold:
                    next_query_data.append(data)
                else:
                    resolved_recordings.append({
                        "artist_name": data["artist_name"],
                        "recording_name": data["recording_name"],
                        "recording_id": hit["recording_id"],
                        "confidence": hit["confidence"],
                        "index": data["index"],
                    })

            if len(next_query_data) == 0:
                break

            query_data = []
            for data in next_query_data:
                recording_name = mc.clean_recording(data["recording_name"])
                if recording_name != data["recording_name"]:
                    print(f'RETRY recording {data["recording_name"]} => {recording_name}')
                    query_data.append({"artist_name": artist_name, "recording_name": recording_name, "index": data["index"]})

                artist_name = mc.clean_artist(data["artist_name"])
                if artist_name != data["artist_name"]:
                    print(f'RETRY artist {data["artist_name"]} => {artist_name}')
                    query_data.append({"artist_name": artist_name, "recording_name": recording_name, "index": data["index"]})

            # If nothing got cleaned, we can finish now
            if len(query_data) == 0:
                break

        return resolved_recordings

    def resolve_playlist(self, match_threshold, recordings=None, jspf_playlist=None):
        """ 
            Given a JSPF playlist or a list of troi recordings, resolve tracks and return a list of resolved recordings.
            threshold is a value between 0 and 1.0 for the percentage score required before a track is matched.
        """

        if recordings is None and jspf_playlist is None:
            raise ValueError("Either recordings or jspf_playlist must be passed.")

        self.db.open_db()
        self.build_index()

        artist_recording_data = []
        if jspf_playlist is not None:
            jspf = read_jspf_playlist(jspf_playlist)
            for i, track in enumerate(jspf["playlist"]["track"]):
                artist_recording_data.append({"artist_name": track["creator"], "recording_name": track["title"]})
        else:
            for rec in recordings:
                artist_recording_data.append({"artist_name": rec.artist.name, "recording_name": rec.name })

        hits = self.resolve_recordings(artist_recording_data, match_threshold)
        hit_index = {hit["index"]: hit for hit in hits}

        recording_ids = [r["recording_id"] for r in hits]
        recordings = Recording.select().where(Recording.id.in_(recording_ids))
        rec_index = {r.id: r for r in recordings}

        results = [None] * len(artist_recording_data)
        for i, artist_recording in enumerate(artist_recording_data):
            if i not in hit_index:
                print("FAIL %s - %s not resolved." % (artist_recording["artist_name"], artist_recording["recording_name"]))
                continue

            hit = hit_index[i]
            rec = rec_index[hit["recording_id"]]
            results[hit["index"]] = rec
            print("OK   %s - %s resolved: %s" % (rec.artist_name, rec.recording_name, os.path.basename(rec.file_path)))

        if len(results) == 0:
            print("Sorry, but no tracks could be resolved, no playlist generated.")
            return

        print(f'\n{len(recordings)} recordings resolved, {len(artist_recording_data) - len(recordings)} not resolved.')

        return results
