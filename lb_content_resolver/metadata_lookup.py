import os
from collections import defaultdict, namedtuple
import datetime
import sys

import peewee
import requests
from tqdm import tqdm

from lb_content_resolver.model.database import db
from lb_content_resolver.model.recording import Recording, RecordingMetadata


RecordingRow = namedtuple('RecordingRow', ('id', 'mbid', 'metadata_id'))


class MetadataLookup:
    '''
    Given the local database, lookup metadata from MusicBrainz to allow local playlist resolution.
    '''

    BATCH_SIZE = 1000

    def lookup(self):
        """
        Iterate over all recordings in the database and call lookup_chunk for chunks of recordings.
        """

        cursor = db.execute_sql("""SELECT recording.id, recording.recording_mbid, recording_metadata.id
                                     FROM recording
                                LEFT JOIN recording_metadata
                                       ON recording.id = recording_metadata.recording_id
                                    WHERE recording_mbid IS NOT NULL
                                 ORDER BY artist_name, release_name""")
        recordings = tuple(
            RecordingRow(id=row[0], mbid=str(row[1]), metadata_id=row[2])
            for row in cursor.fetchall()
        )

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
        mbid_to_recording = {}
        for rec in recordings:
            mbid_to_recording[rec.mbid] = rec
            args.append({"[recording_mbid]": rec.mbid})

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
                recording_tags[mbid] = {"artist": [], "release-group": [], "recording": []}

            recording_tags[mbid][row["source"]].append(row["tag"])
            tags.add(row["tag"])

        self.pbar.update(len(recordings))

        tags = list(tags)
        with db.atomic():

            # This DB code is pretty messy -- things I take for granted with Postgres are not
            # available in SQLite or the PeeWee ORM. But, this might be ok, since we're not
            # updating millions of rows constantly.

            # First update recording_metadata table
            for mbid in set(recording_pop):
                recording = mbid_to_recording[mbid]
                if recording.metadata_id is None:
                    recording_metadata = RecordingMetadata.create(recording=recording.id,
                                                                  popularity=recording_pop[mbid],
                                                                  last_updated=datetime.datetime.now())
                    recording_metadata.save()
                else:
                    recording_metadata = RecordingMetadata.replace(id=recording.metadata_id,
                                                                   recording=recording.id,
                                                                   popularity=recording_pop[mbid],
                                                                   last_updated=datetime.datetime.now())

                    recording_metadata.execute()

            # Next delete recording_tags
            for mbid in set(recording_tags):
                db.execute_sql("""DELETE FROM recording_tag WHERE recording_id in (
                                       SELECT id FROM recording WHERE recording_mbid = ?
                                  )""", (mbid,))
            # This is the better way to insert the tags into the DB, but on some installations
            # of Sqlite/Python the UPSERT is not supported. Once it is widely supported,
            # remove the section below and uncomment this.
            #tag_ids = {}
            #for tag in tags:
            #    cursor = db.execute_sql("""INSERT INTO tag (name)
            #                                    VALUES (?)
            #                 ON CONFLICT DO UPDATE SET name = ? RETURNING id""", (tag,tag))
            #    row = cursor.fetchone()
            #    tag_ids[tag] = row[0]

            # insert new recording tags
            tag_ids = {}
            for tag in tags:
                db.execute_sql("""INSERT OR IGNORE INTO tag (name) VALUES (?)""", (tag,))

            tag_str = ",".join([ "'%s'" % t.replace("'", "''") for t in tags])
            cursor = db.execute_sql("""SELECT id, name FROM tag WHERE name IN (%s)""" % tag_str)
            for row in cursor.fetchall():
                tag_ids[row[1]] = row[0]

            # insert recording_tag rows
            for row in r.json():
                recording = mbid_to_recording[row["recording_mbid"]]
                now = datetime.datetime.now()
                db.execute_sql("""INSERT INTO recording_tag (recording_id, tag_id, entity, last_updated)
                                       VALUES (?, ?, ?, ?)""", (recording.id, tag_ids[row["tag"]], row["source"], now))

        return True
