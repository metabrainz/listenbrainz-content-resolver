import os
from collections import defaultdict
import datetime
import sys

import peewee
import requests

from lb_content_resolver.model.database import db
from lb_content_resolver.model.recording import Recording, RecordingMetadata
from troi.recording_search_service import RecordingSearchByTagService
from troi.splitter import plist

# TODO: Right now this only works for subsonic tracks!
# TODO: OR TAG SEARCH:  ['4ad', 'hindi'] -- hindi has one result, but that does not appear in the output.


class LocalRecordingSearchByTagService(RecordingSearchByTagService):
    ''' 
    Given the local database, search for recordings that meet given tag criteria
    '''

    def __init__(self, db):
        RecordingSearchByTagService.__init__(self)
        self.db = db

    def search(self, tags, operator, begin_percent, end_percent, num_recordings):
        """
        """

        if operator == "or":
            query, params, pop_clause = self.or_search(tags)
        else:
            query, params, pop_clause = self.and_search(tags)

        self.db.open_db()
        placeholders = ",".join(("?",) * len(tags))
        cursor = db.execute_sql(query % (placeholders, pop_clause), params)

        # Break the data into over, matching and under (percent) groups
        matching_recordings = []
        over_recordings = []
        under_recordings = []
        for rec in cursor.fetchall():
            recording = { "recording_mbid": rec[0],
                          "percent": rec[1],
                          "subsonic_id": rec[2],
                          "recording_name": rec[3],
                          "artist_name": rec[4] }

            if rec[1] >= begin_percent:
                if rec[1] < end_percent:
                    matching_recordings.append(recording)
                else:
                    over_recordings.append(recording)
            else:
                under_recordings.append(recording)

        if len(matching_recordings) >= num_recordings:
            return plist(matching_recordings)

        def print_result(items):
            for i in items:
                print("%-30s %-30s %d%%" % (i["recording_name"][:29],
                    i["artist_name"][:29],
                    i["percent"] * 100))
            print()

#        print("begin %d%% end %d%%" % (begin_percent * 100, end_percent * 100))
#        print("under")
#        print_result(under_recordings)
#        print("matches")
#        print_result(matching_recordings)
#        print("over")
#        print_result(over_recordings)

        # Keep adding the best matches until we (hopefully) get our desired number of recordings
        while len(matching_recordings) < num_recordings:
            if under_recordings:
                under_diff = begin_percent - under_recordings[-1]["percent"]
            else:
                under_diff = 1.0

            if over_recordings:
                over_diff = over_recordings[-1]["percent"] - end_percent
            else:
                over_diff = 1.0

            if over_diff == 1.0 and under_diff == 1.0:
                break

            if under_diff < over_diff:
                matching_recordings.insert(0, under_recordings.pop(-1))
            else:
                matching_recordings.insert(len(matching_recordings), over_recordings.pop(0)) 

#        print("final matches")
#        print_result(matching_recordings)


        return plist(matching_recordings)


    def or_search(self, tags, min_popularity=None, max_popularity=None):
        query = """WITH recording_ids AS (
                        SELECT DISTINCT(recording_id)
                          FROM tag
                          JOIN recording_tag
                            ON recording_tag.tag_id = tag.id
                          JOIN recording
                            ON recording.id = recording_tag.recording_id
                         WHERE name in (%s)
                   )
                       SELECT recording_mbid
                            , popularity AS percent
                            , subsonic_id
                            , recording_name
                            , artist_name
                         FROM recording
                         JOIN recording_ids
                           ON recording.id = recording_ids.recording_id
                         JOIN recording_metadata
                           ON recording.id = recording_metadata.recording_id
                         JOIN recording_subsonic
                           ON recording.id = recording_subsonic.recording_id
                           %s
                     ORDER BY popularity DESC"""

        if min_popularity is not None and max_popularity is not None:
            pop_clause = """WHERE popularity >= %.4f AND popularity < %.4f""" % \
                (min_popularity, max_popularity)
        else:
            pop_clause = ""

        return query, [*tags], pop_clause

    def and_search(self, tags, min_popularity=None, max_popularity=None):
        # todo: remove fetch name and artist
        query = """WITH recording_tags AS (
                        SELECT DISTINCT recording.id AS recording_id
                             , tag.name AS tag_name
                          FROM tag
                          JOIN recording_tag
                            ON recording_tag.tag_id = tag.id
                          JOIN recording
                            ON recording.id = recording_tag.recording_id
                         WHERE name in (%s)
                         ORDER BY recording.id
                   ), recording_ids AS ( 
                       SELECT recording_tags.recording_id
                         FROM recording_tags
                         JOIN recording_metadata
                           ON recording_tags.recording_id = recording_metadata.recording_id
                     GROUP BY recording_tags.recording_id
                       HAVING count(recording_tags.tag_name) = ?
                   ) 
                       SELECT recording_mbid
                            , popularity AS percent
                            , subsonic_id
                            , recording_name
                            , artist_name
                         FROM recording
                         JOIN recording_ids
                           ON recording.id = recording_ids.recording_id
                         JOIN recording_metadata
                           ON recording.id = recording_metadata.recording_id
                         JOIN recording_subsonic
                           ON recording.id = recording_subsonic.recording_id
                           %s
                     ORDER BY popularity DESC"""

        if min_popularity is not None and max_popularity is not None:
            pop_clause = """WHERE popularity >= %.4f AND popularity < %.4f""" % \
                (min_popularity, max_popularity)
        else:
            pop_clause = ""

        return query, (*tags, len(tags)), pop_clause
