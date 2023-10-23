import os
from collections import defaultdict
import datetime
import sys
from uuid import UUID

import peewee
import requests

from lb_content_resolver.model.database import db
from lb_content_resolver.model.recording import Recording, RecordingMetadata


class MetadataLookup:
    ''' 
    Given the local database, lookup metadata from MusicBrainz to allow local playlist resolution.
    '''

    def __init__(self, db):
        self.db = db

    def lookup(self):
        """
        """

        self.db.open_db()
        args = []
        mbid_to_id_index = {}

        cursor = db.execute_sql("""SELECT recording.id, recording.recording_mbid, popularity
                                     FROM recording 
                                LEFT JOIN recordingmetadata
                                       ON recording.id = recordingmetadata.recording_id""")
        for row in cursor.fetchall():
            args.append({ "[recording_mbid]": str(row[1]) })
            mbid_to_id_index[str(row[1])] = row
            if len(args) == 1000:
                break

        r = requests.post("https://labs.api.listenbrainz.org/bulk-tag-lookup/json", json=args)
        if r.status_code != 200:
            print("Fail: %d %s" % (r.status_code, r.text))
            return

        recording_pop = {}
        recording_tags = {}
        for row in r.json():
            print("%s, %s, %s" % (row["recording_mbid"], row["tag"], row["source"]))

            mbid = str(row["recording_mbid"])
            recording_pop[mbid] = row["percent"]
            if mbid not in recording_tags:
                recording_tags[mbid] = { "artist": [], "release-group": [], "recording": [] }

            recording_tags[mbid][row["source"]].append(row["tag"])

        print(f"{len(args)} db rows, {len(r.json())} api rows")
        print(mbid_to_id_index)

        with db.atomic():
            mbids = recording_pop.keys()
            for mbid in list(set(mbids)):
                print(f"update {mbid}")
                mbid = str(mbid)
                recording = mbid_to_id_index[mbid]
                m = recording.metadata
                print(m.last_updated)
                if recording.metadata.last_updated is None:
                    print("create new")
                    recording.metadata = RecordingMetadata.create(recording=recording.id,
                                                                  popularity=recording_pop[mbid],
                                                                  last_updated=datetime.datetime.now())
                    recording.save()
                else:
                    print("update existing")
                    recording.metadata.popularity = row["percent"]
                    recording.metadata.last_updated = datetime.datetime.now()
                    recording.save()

#            for row in r.json():
