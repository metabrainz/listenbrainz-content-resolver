import os
import json
from collections import defaultdict
import datetime
import sys

import peewee
import requests

from lb_content_resolver.model.database import db
from lb_content_resolver.model.recording import Recording, RecordingMetadata
from troi.recording_search_service import RecordingSearchByTagService
from troi.splitter import plist


class FindDuplicates:
    ''' 
       Class to fetch recordings that are duplicate in the database.
    '''

    def __init__(self, db):
        self.db = db

    def get_duplicate_recordings(self, include_different_releases):
        """
           Return a list of (recording_name
        """

        if include_different_releases:
            query = """SELECT recording_name
                            , release_name
                            , artist_name
                            , recording_mbid
                            , json_group_array(file_path) AS file_paths
                            , COUNT(*) AS cnt
                         FROM recording
                     GROUP BY recording_mbid
                            , release_mbid
                       HAVING cnt > 1 
                     ORDER BY cnt DESC, artist_name, recording_name"""
        else:
            query = """SELECT recording_name
                            , release_name
                            , artist_name
                            , recording_mbid
                            , json_group_array(file_path) AS file_paths
                            , COUNT(*) AS cnt
                         FROM recording
                     GROUP BY recording_mbid
                       HAVING cnt > 1 
                     ORDER BY cnt DESC, artist_name, recording_name"""

        self.db.open_db()

        return [ (r[0], r[1], r[2], r[3], json.loads(r[4]), r[5]) for r in db.execute_sql(query).fetchall() ]

    
    def print_duplicate_recordings(self, include_different_releases=True):

        total = 0
        dups = self.get_duplicate_recordings(include_different_releases)
        for dup in dups:
            print("%d duplicates of '%s' by '%s'" % (dup[5], dup[0], dup[2]))
            for f in dup[4]:
                print("   %s" % f)
                total += 1
            print()

        print()
        print("%d recordings had a total of %d duplicates." % (len(dups), total))
