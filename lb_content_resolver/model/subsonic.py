import datetime
from peewee import *
from lb_content_resolver.model.database import db
from lb_content_resolver.model.recording import Recording


class RecordingSubsonic(Model):
    """
        A table for storing subsonic track ids, linked to recordings. 
    """

    class Meta:
        database = db
        table_name = "recording_subsonic"

    id = AutoField()
    recording = ForeignKeyField(Recording, backref="metadata")

    subsonic = TextField()
    last_updated = DateTimeField(null=False, default=datetime.datetime.now)

    def __repr__(self):
        return "<RecordingMetadata('%d','%.3f')>" % (self.recording or 0, self.subsonic)
