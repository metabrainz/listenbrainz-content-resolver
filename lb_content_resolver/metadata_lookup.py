import os
from collections import defaultdict
import datetime
import sys

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

        cursor = db.execute_sql("""SELECT recording.id, recording.recording_mbid, recording_metadata.id, popularity
                                     FROM recording 
                                LEFT JOIN recording_metadata
                                       ON recording.id = recording_metadata.recording_id""")
        for row in cursor.fetchall():
            mbid = str(row[1])
            args.append({ "[recording_mbid]": mbid })
            mbid_to_id_index[mbid] = row
            if len(args) == 1000:
                break

        r = requests.post("https://labs.api.listenbrainz.org/bulk-tag-lookup/json", json=args)
        if r.status_code != 200:
            print("Fail: %d %s" % (r.status_code, r.text))
            return

        recording_pop = {}
        recording_tags = {}  ## still needed? TODO
        tags = set()
        for row in r.json():
            print("%s, %s, %s" % (row["recording_mbid"], row["tag"], row["source"]))

            mbid = str(row["recording_mbid"])
            recording_pop[mbid] = row["percent"]
            if mbid not in recording_tags:
                recording_tags[mbid] = { "artist": [], "release-group": [], "recording": [] }

            recording_tags[mbid][row["source"]].append(row["tag"])
            tags.add(row["tag"])

        tags = list(tags)

        print(f"{len(args)} db rows, {len(r.json())} api rows")

        with db.atomic():

            # First update recording_metadata table
            mbids = recording_pop.keys()
            for mbid in list(set(mbids)):
                print(f"update {mbid}")
                mbid = str(mbid)
                row = mbid_to_id_index[mbid]
                if row[3] is None:
                    recording_metadata = RecordingMetadata.create(recording=row[0],
                                                                  popularity=recording_pop[mbid],
                                                                  last_updated=datetime.datetime.now())
                    recording_metadata.save()
                else:
                    recording_metadata = RecordingMetadata.replace(id=row[2],
                                                                  recording=row[0],
                                                                  popularity=recording_pop[mbid],
                                                                  last_updated=datetime.datetime.now())

                    recording_metadata.execute()

            # Next delete recording_tags
            mbids = recording_tags.keys()
            for mbid in mbids:
                db.execute_sql("""DELETE FROM recording_tag WHERE recording_id in (
                                       SELECT id FROM recording WHERE recording_mbid = ?
                                  )""", (mbid,))

            # Finally, insert new recording tags
            for tag in tags:
                db.execute_sql("""INSERT OR IGNORE INTO tag (name) VALUES (?)""", (tag,))

            for row in r.json():
                print("%s, %s, %s" % (row["recording_mbid"], row["tag"], row["source"]))
                row_id = mbid_to_id_index[row["recording_mbid"]]
                db.execute_sql("""INSERT INTO recording_tag (recording_id, tag, entity)
                                       VALUES (?, ?, ?)""", (row_id, row["tag"], row["source"]))
