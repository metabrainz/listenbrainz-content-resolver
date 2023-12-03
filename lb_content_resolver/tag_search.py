import os
from collections import defaultdict
import datetime
import sys

import peewee
import requests

from lb_content_resolver.model.database import db
from lb_content_resolver.model.recording import Recording, RecordingMetadata


class TagSearch:
    ''' 
    Given the local database, search for tags that meet given criteria
    '''

    def __init__(self, db):
        self.db = db

    def search(self, tags, operator="or"):
        """
        """

        if operator == "or":
            query, params = self.or_search(tags, .1, .9)
        else:
            query, params = self.and_search(tags, .1, .9)

        self.db.open_db()
        placeholders = ",".join(("?",) * len(tags))
        print(query % placeholders)
        cursor = db.execute_sql(query % placeholders, params)
        return cursor.fetchall()

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
                       SELECT recording.id
                            , recording_name
                            , popularity
                         FROM recording
                         JOIN recording_ids
                           ON recording.id = recording_ids.recording_id
                         JOIN recording_metadata
                           ON recording.id = recording_metadata.recording_id
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
                       SELECT recording.id
                            , recording_name
                            , popularity
                         FROM recording
                         JOIN recording_ids
                           ON recording.id = recording_ids.recording_id
                         JOIN recording_metadata
                           ON recording.id = recording_metadata.recording_id
                        WHERE popularity >= ?
                          AND popularity < ?
                     ORDER BY popularity DESC"""
        return query, (*tags, len(tags), min_popularity, max_popularity)
