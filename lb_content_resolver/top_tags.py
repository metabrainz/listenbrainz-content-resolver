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


class TopTags:
    '''
       Class to fetch top tags
    '''

    def get_top_tags(self, limit=50):
        """
        """

        query = """SELECT tag.name
                        , COUNT(tag.id) AS cnt
                     FROM tag
                     JOIN recording_tag
                       ON recording_tag.tag_id = tag.id
                     JOIN recording
                       ON recording_tag.recording_id = recording.id
                 GROUP BY tag.name
                 ORDER BY cnt DESC
                    LIMIT ?"""

        cursor = db.execute_sql(query, (limit,))

        top_tags = []
        for rec in cursor.fetchall():
            top_tags.append({"tag": rec[0], "count": rec[1]})

        return top_tags

    def print_top_tags(self, limit=50):

        top_tags = self.get_top_tags(limit)
        for tt in top_tags:
            print("%-40s %d" % (tt["tag"], tt["count"]))
        print()

    def print_top_tags_tightly(self, limit=250):

        top_tags = self.get_top_tags(limit)

        print("; ".join(["%s %s" % (tt["tag"], tt["count"]) for tt in top_tags]))
