import os
import datetime
import sys
from uuid import UUID

import peewee

from lb_content_resolver.model.database import db, setup_db
from lb_content_resolver.model.recording import Recording
from lb_content_resolver.model.subsonic import RecordingSubsonic
from lb_content_resolver.unresolved_recording import UnresolvedRecordingTracker
from lb_content_resolver.fuzzy_index import FuzzyIndex
from lb_matching_tools.cleaner import MetadataCleaner
from lb_content_resolver.playlist import read_jspf_playlist
from lb_content_resolver.utils import bcolors


class ContentResolver:
    '''
    Scan a given path and enter/update the metadata in the search index
    '''

    def __init__(self):
        self.fuzzy_index = None

    def get_artist_recording_metadata(self):
        """
            Fetch the metadata needed to build a fuzzy search index.
        """

        artist_recording_data = []
        for recording in Recording.select():
            artist_recording_data.append((recording.artist_name, recording.recording_name, recording.id))

        return artist_recording_data

    def build_index(self):
        """
            Fetch the data from the DB and then build the fuzzy lookup index.
        """

        artist_recording_data = self.get_artist_recording_metadata()
        for recording in Recording.select():
            artist_recording_data.append((recording.artist_name, recording.recording_name, recording.id))

        self.fuzzy_index = FuzzyIndex()
        self.fuzzy_index.build(artist_recording_data)

    def resolve_recordings(self, query_data, match_threshold):
        """
        Given a list of dicts with artist_name, recording_name, recording_mbid in query data and
        a matching threshold, attempt to match recordings by looking them up in the fuzzy index.
        """

        resolved_recordings = []
        unresolved_recording_mbids = []

        # Set indexes in the data so we can correlate matches
        for i, data in enumerate(query_data):
            data["index"] = i

        mc = MetadataCleaner()
        while True:
            next_query_data = []
            hits = self.fuzzy_index.search(query_data)
            for hit, data in zip(hits, query_data):

                # If we resolved this recording via MBID in a previous step, accept that as a match
                if "recording_id" in data:
                    resolved_recordings.append({
                        "artist_name": data["artist_name"],
                        "recording_name": data["recording_name"],
                        "recording_mbid": data["recording_mbid"],
                        "recording_id": data["recording_id"],
                        "confidence": 1.0,
                        "index": data["index"],
                        "method": "MBID"
                    })
                    continue

                # if not, proceed to examine the match that metadata lookup gave us
                if hit["confidence"] < match_threshold:
                    next_query_data.append(data)
                    unresolved_recording_mbids.append(data["recording_mbid"])
                else:
                    resolved_recordings.append({
                        "artist_name": data["artist_name"],
                        "recording_name": data["recording_name"],
                        "recording_mbid": data["recording_mbid"],
                        "recording_id": hit["recording_id"],
                        "confidence": hit["confidence"],
                        "index": data["index"],
                        "method": "FUZZY"
                    })

            if len(next_query_data) == 0:
                break

            query_data = []
            for data in next_query_data:
                recording_name = mc.clean_recording(data["recording_name"])
                artist_name = mc.clean_artist(data["artist_name"])
                if recording_name != data["recording_name"]:
                    query_data.append({"artist_name": artist_name,
                                       "recording_name": recording_name,
                                       "recording_mbid": data["recording_mbid"],
                                       "index": data["index"]})

                if artist_name != data["artist_name"]:
                    query_data.append({"artist_name": artist_name,
                                       "recording_name": recording_name,
                                       "recording_mbid": data["recording_mbid"],
                                       "index": data["index"]})

            # If nothing got cleaned, we can finish now
            if len(query_data) == 0:
                break

        ur = UnresolvedRecordingTracker()
        ur.add(unresolved_recording_mbids)

        return resolved_recordings

    def resolve_recording_by_mbid(self, artist_recording_data):
        """
            Given artist_recording_data, check to see if any of the recording MBIDs are
            in the local collection. If so, load the recording.id for it so it can be
            skipped later.
        """

        recording_index = {}
        for r in artist_recording_data:
            if "recording_mbid" in r:
                recording_index[r["recording_mbid"]] = r

        recording_mbids = list(recording_index.keys())
        recordings = Recording \
            .select(Recording) \
            .where(Recording.recording_mbid.in_(recording_mbids)) \
            .dicts()

        for recording in recordings:
            if recording["recording_mbid"] in recording_index:
                recording_index[recording["recording_mbid"]]["recording_id"] = recording["id"]

        return artist_recording_data

    def resolve_playlist(self, match_threshold, recordings=None, jspf_playlist=None):
        """
            Given a JSPF playlist or a list of troi recordings, resolve tracks and return a list of resolved recordings.
            threshold is a value between 0 and 1.0 for the percentage score required before a track is matched.
        """

        if recordings is None and jspf_playlist is None:
            raise ValueError("Either recordings or jspf_playlist must be passed.")

        artist_recording_data = []
        if jspf_playlist is not None:
            if len(jspf_playlist["playlist"]["track"]) == 0:
                return []
            for i, track in enumerate(jspf_playlist["playlist"]["track"]):
                artist_recording_data.append({"artist_name": track["creator"],
                                              "recording_name": track["title"],
                                              "recording_mbid": track["identifier"][34:]})
        else:
            if not recordings:
                return []
            for rec in recordings:
                artist_recording_data.append({"artist_name": rec.artist.name,
                                              "recording_name": rec.name,
                                              "recording_mbid": rec.mbid})

        # See what we can resolve using MBIDs
        artist_recording_data = self.resolve_recording_by_mbid(artist_recording_data)

        self.build_index()

        hits = self.resolve_recordings(artist_recording_data, match_threshold)
        hit_index = {hit["index"]: hit for hit in hits}

        recording_ids = [r["recording_id"] for r in hits]
        recordings = Recording \
            .select(Recording, RecordingSubsonic.subsonic_id) \
            .join(RecordingSubsonic, peewee.JOIN.LEFT_OUTER, on=(Recording.id == RecordingSubsonic.recording_id)) \
            .where(Recording.id.in_(recording_ids)) \
            .dicts()
        rec_index = {r["id"]: r for r in recordings}

        print("       %-40s %-40s %-40s" % ("RECORDING", "RELEASE", "ARTIST"))
        results = [None] * len(artist_recording_data)
        unresolved_recordings = []
        for i, artist_recording in enumerate(artist_recording_data):
            if i not in hit_index:
                print(bcolors.FAIL + "FAIL " + bcolors.ENDC + "  %-40s %-40s %-40s" % (artist_recording["recording_name"][:39], "",
                                                                                       artist_recording["artist_name"][:39]))
                unresolved_recordings.append(artist_recording["recording_mbid"])
                continue

            hit = hit_index[i]
            rec = rec_index[hit["recording_id"]]
            results[hit["index"]] = rec
            print(bcolors.OKGREEN + ("%-5s" % hit["method"]) + bcolors.ENDC +
                  "  %-40s %-40s %-40s" % (artist_recording["recording_name"][:39], "",
                                           artist_recording["artist_name"][:39]))
            print("       %-40s %-40s %-40s" % (rec["recording_name"][:39],
                                                rec["release_name"][:39],
                                                rec["artist_name"][:39]))

        if len(results) == 0:
            print("Sorry, but no tracks could be resolved, no playlist generated.")
            return []

        print(f'\n{len(recordings)} recordings resolved, {len(artist_recording_data) - len(recordings)} not resolved.')

        return results
