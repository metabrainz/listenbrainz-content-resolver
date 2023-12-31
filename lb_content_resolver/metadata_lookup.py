import os
from collections import defaultdict
import datetime
import sys

import peewee
import requests
from tqdm import tqdm

from lb_content_resolver.model.database import db
from lb_content_resolver.model.recording import Recording, RecordingMetadata


class MetadataLookup:
    ''' 
    Given the local database, lookup metadata from MusicBrainz to allow local playlist resolution.
    '''

    BATCH_SIZE = 1000

    def __init__(self, db):
        self.db = db

    def lookup(self):
        """
        Iterate over all recordings in the database and call lookup_chunk for chunks of recordings.
        """

        self.db.open_db()

        cursor = db.execute_sql("""SELECT recording.id, recording.recording_mbid, recording_metadata.id
                                     FROM recording 
                                LEFT JOIN recording_metadata
                                       ON recording.id = recording_metadata.recording_id
                                    WHERE recording_mbid IS NOT NULL
                                 ORDER BY artist_name, release_name""")
        recordings = []
        for row in cursor.fetchall():
            recordings.append(row)

        print("[ %d recordings to lookup ]" % len(recordings))

        offset = 0
        with tqdm(total=len(recordings)) as self.pbar:
            while offset <= len(recordings):
                self.process_recordings(recordings[offset:offset+self.BATCH_SIZE])
                offset += self.BATCH_SIZE


    def process_recordings(self, recordings):
        """
            This function carries out the actual lookup of the metadata and inserting the
            popularity and tags into the DB for the given chunk of recordings.
        """

        args = []
        mbid_to_id_index = {}
        for rec in recordings:
            mbid_to_id_index[ str(rec[1])] = rec
            args.append({ "[recording_mbid]": str(rec[1]) })

        r = requests.post("https://labs.api.listenbrainz.org/bulk-tag-lookup/json", json=args)
        if r.status_code != 200:
            print("Fail: %d %s" % (r.status_code, r.text))
            return False

        recording_pop = {}
        recording_tags = {}
        tags = set()
        for row in r.json():
            mbid = str(row["recording_mbid"])
            recording_pop[mbid] = row["percent"]
            if mbid not in recording_tags:
                recording_tags[mbid] = { "artist": [], "release-group": [], "recording": [] }

            recording_tags[mbid][row["source"]].append(row["tag"])
            tags.add(row["tag"])

        self.pbar.update(len(recordings))

        tags = list(tags)
        with db.atomic():

            # This DB code is pretty messy -- things I take for granted with Postgres are not
            # available in SQLite or the PeeWee ORM. But, this might be ok, since we're not 
            # updating millions of rows constantly.

            # First update recording_metadata table
            mbids = recording_pop.keys()
            for mbid in list(set(mbids)):
                mbid = str(mbid)
                row = mbid_to_id_index[mbid]
                if row[2] is None:
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

            # insert new recording tags
            tag_ids = {}
            for tag in tags:
                cursor = db.execute_sql("""INSERT INTO tag (name)
                                                VALUES (?)
                             ON CONFLICT DO UPDATE SET name = ? RETURNING id""", (tag,tag))
                row = cursor.fetchone()
                tag_ids[tag] = row[0]

            # insert recording_tag rows
            for row in r.json():
                row_id = mbid_to_id_index[row["recording_mbid"]]
                now = datetime.datetime.now()
                db.execute_sql("""INSERT INTO recording_tag (recording_id, tag_id, entity, last_updated)
                                       VALUES (?, ?, ?, ?)""", (row_id[0], tag_ids[row["tag"]], row["source"], now))

        return True
