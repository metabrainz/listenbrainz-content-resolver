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


class LocalRecordingSearchByTagService(RecordingSearchByTagService):
    ''' 
    Given the local database, search for recordings that meet given tag criteria
    '''

    def __init__(self, db):
        RecordingSearchByTagService.__init__(self)
        self.db = db

    def search(self, tags, operator, begin_percent, end_percent):
        """
        """

        if operator == "or":
            query, params = self.or_search(tags, begin_percent, end_percent)
        else:
            query, params = self.and_search(tags, begin_percent, end_percent)

        self.db.open_db()
        placeholders = ",".join(("?",) * len(tags))
        cursor = db.execute_sql(query % placeholders, params)

        recordings = plist()
        for rec in cursor.fetchall():
            recordings.append({ "recording_mbid": rec[0], "percent": rec[1], "subsonic_id": rec[2] })

        return recordings


    def or_search(self, tags, min_popularity, max_popularity):
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
                         FROM recording
                         JOIN recording_ids
                           ON recording.id = recording_ids.recording_id
                         JOIN recording_metadata
                           ON recording.id = recording_metadata.recording_id
                         JOIN recording_subsonic
                           ON recording.id = recording_subsonic.recording_id
                        WHERE popularity >= ?
                          AND popularity < ?
                     ORDER BY popularity DESC"""
        return query, (*tags, min_popularity, max_popularity)

    def and_search(self, tags, min_popularity, max_popularity):
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
                         FROM recording
                         JOIN recording_ids
                           ON recording.id = recording_ids.recording_id
                         JOIN recording_metadata
                           ON recording.id = recording_metadata.recording_id
                         JOIN recording_subsonic
                           ON recording.id = recording_subsonic.recording_id
                        WHERE popularity >= ?
                          AND popularity < ?
                     ORDER BY popularity DESC"""
        return query, (*tags, len(tags), min_popularity, max_popularity)
