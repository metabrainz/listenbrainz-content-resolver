import os
import datetime
import requests
import sys
from math import ceil

import peewee

from lb_content_resolver.model.database import db
from lb_content_resolver.model.unresolved_recording import UnresolvedRecording


class UnresolvedRecordingTracker:
    ''' 
        This class keeps track of recordings that were not resolved when 
        a playlist was resolved. This will allow us to give recommendations
        on which albums to add to their collection to resolve more recordings.
    '''

    LOOKUP_BATCH_SIZE = 50

    def __init__(self):
        pass

    @staticmethod
    def chunks(lst, n):
        """Yield successive n-sized chunks from lst."""
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    def add(self, recording_mbids):
        """
            Add one or more recording MBIDs to the unresolved recordings track. If this has
            previously been unresolved, increment the count for the number 
            of times it has been unresolved.
        """

        query = """INSERT INTO unresolved_recording (recording_mbid, last_updated, lookup_count)
                        VALUES (?, ?, 1)
         ON CONFLICT DO UPDATE SET lookup_count = EXCLUDED.lookup_count + 1"""

        with db.atomic() as transaction:
            for mbid in recording_mbids:
                db.execute_sql(query, (mbid, datetime.datetime.now()))

    def get(self, num_items, lookup_count):

        if lookup_count is not None:
            where_clause = f"WHERE lookup_count >= {lookup_count}"
        else:
            where_clause = ""

        query = f"""SELECT recording_mbid
                         , lookup_count
                      FROM unresolved_recording
                           {where_clause}
                  ORDER BY lookup_count DESC"""

        cursor = db.execute_sql(query)
        recording_mbids = []
        lookup_counts = {}
        for row in cursor.fetchall():
            recording_mbids.append(row[0])
            lookup_counts[row[0]] = row[1]

        recording_data = {}
        for chunk in self.chunks(recording_mbids, self.LOOKUP_BATCH_SIZE):
            args = ",".join(chunk)

            params = { "recording_mbids": args, "inc": "artist release" }
            while True:
                r = requests.get("https://api.listenbrainz.org/1/metadata/recording", params=params)
                if r.status_code != 200:
                    print("Failed to fetch metadata for recordings: ", r.text)
                    return []

                if r.status_code == 429:
                    sleep(1)
                    continue

                break
            recording_data.update(dict(r.json()))

        results = []
        for mbid in recording_mbids:
            rec = recording_data[mbid]
            results.append({
                "artist_name": rec["artist"]["name"],
                "artists": rec["artist"]["artists"],
                "release_name": rec["release"]["name"],
                "release_mbid": rec["release"]["mbid"],
                "release_group_mbid": rec["release"]["release_group_mbid"],
                "recording_name": "Contact",
                "recording_mbid": mbid,
                "lookup_count": lookup_counts[mbid]
            })

        return results
