import os
from collections import defaultdict
import datetime
import sys

import peewee
import requests

from lb_content_resolver.model.database import db
from lb_content_resolver.model.recording import Recording, RecordingMetadata
from troi.recording_search_service import RecordingSearchByArtistService
from troi.splitter import plist
from troi import Recording as TroiRecording


class LocalRecordingSearchByArtistService(RecordingSearchByArtistService):
    ''' 
    Given the local database, search for artists that meet given tag criteria
    '''

    def __init__(self, db):
        RecordingSearchByArtistService.__init__(self)
        self.db = db

    def search(self, artist_mbids, begin_percent, end_percent, num_recordings):
        """
        Perform an artist search. Parameters:

        tags - a list of artist_mbids for which to search recordings
        begin_percent - if many recordings match the above parameters, return only
                        recordings that have a minimum popularity percent score 
                        of begin_percent.
        end_percent - if many recordings match the above parameters, return only
                      recordings that have a maximum popularity percent score 
                      of end_percent.
        num_recordings - ideally return these many recordings

        If only few recordings match, the begin_percent and end_percent are
        ignored.
        """

        query = """SELECT popularity
                        , recording_mbid
                        , artist_mbid
                        , subsonic_id
                     FROM recording
                     JOIN recording_metadata
                       ON recording.id = recording_metadata.recording_id
                     JOIN recording_subsonic
                       ON recording.id = recording_subsonic.recording_id
                    WHERE artist_mbid in (%s)
                 ORDER BY artist_mbid
                        , popularity"""

        self.db.open_db()
        placeholders = ",".join(("?", ) * len(artist_mbids))
        cursor = db.execute_sql(query % placeholders, params=tuple(artist_mbids))

        artists = defaultdict(list)
        for rec in cursor.fetchall():
            artists[rec[2]].append({"popularity": rec[0], "recording_mbid": rec[1], "artist_mbid": rec[2], "subsonic_id": rec[3]})

        for artist in artists:
            artists[artist] = self.fetch_and_select_on_popularity(artists[artist], begin_percent, end_percent, num_recordings)

        return artists


    # TODO: use this in both tag and artist search classes
    def fetch_and_select_on_popularity(self, recordings, begin_percent, end_percent, num_recordings):
        """
            Break the data into over, matching and under (percent) groups
        """

        matching_recordings = []
        over_recordings = []
        under_recordings = []
        for rec in recordings:
            if rec["popularity"] >= begin_percent:
                if rec["popularity"] < end_percent:
                    matching_recordings.append(rec)
                else:
                    over_recordings.append(rec)
            else:
                under_recordings.append(rec)

        # If we have enough recordings, skip the extending part
        if len(matching_recordings) < num_recordings:
            # We don't have enough recordings, see if we can pick the ones outside
            # of our desired range in a best effort to make a playlist.
            # Keep adding the best matches until we (hopefully) get our desired number of recordings
            while len(matching_recordings) < num_recordings:
                if under_recordings:
                    under_diff = begin_percent - under_recordings[-1]["popularity"]
                else:
                    under_diff = 1.0

                if over_recordings:
                    over_diff = over_recordings[-1]["popularity"] - end_percent
                else:
                    over_diff = 1.0

                if over_diff == 1.0 and under_diff == 1.0:
                    break

                if under_diff < over_diff:
                    matching_recordings.insert(0, under_recordings.pop(-1))
                else:
                    matching_recordings.insert(len(matching_recordings), over_recordings.pop(0))

        # Convert results into recordings
        results = plist()
        for rec in matching_recordings:
            r = TroiRecording(mbid=rec["recording_mbid"])
            if "subsonic_id" in rec:
                r.musicbrainz={"subsonic_id": rec["subsonic_id"]}

            results.append(r)

        return results
