import os
import datetime
import sys

import peewee

from lb_content_resolver.model.database import db
from lb_content_resolver.model.unresolved_recording import UnresolvedRecording


class UnresolvedRecordingTracker:
    ''' 
        This class keeps track of recordings that were not resolved when 
        a playlist was resolved. This will allow us to give recommendations
        on which albums to add to their collection to resolve more recordings.
    '''

    def __init__(self):
        pass

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
