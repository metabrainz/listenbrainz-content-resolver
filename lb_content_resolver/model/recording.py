import datetime
from peewee import *
from lb_content_resolver.model.database import db


class Recording(Model):
    """
    Basic metadata information about a recording on disk (a track).
    """

    class Meta:
        database = db

    id = AutoField()
    file_path = TextField(null=False, unique=True)
    mtime = TimestampField(null=False)

    artist_name = TextField(null=True)
    release_name = TextField(null=True)
    recording_name = TextField(null=True)

    # Not using the UUIDField here, since it annoyingly removes '-' from the UUID.
    recording_mbid = TextField(null=True, index=True)
    artist_mbid = TextField(null=True, index=True)
    release_mbid = TextField(null=True, index=True)

    duration = IntegerField(null=True)
    track_num = IntegerField(null=True)

    def __repr__(self):
        return "<Recording('%s','%s')>" % (self.recording_mbid or "", self.recording_name)


class RecordingMetadata(Model):
    """
    Additional metadata for recorings: popularity. In future additional fields
    like release date and release country could be added to this table.
    """

    class Meta:
        database = db
        table_name = "recording_metadata"

    id = AutoField()
    recording = ForeignKeyField(Recording, backref="metadata")

    popularity = FloatField()
    last_updated = DateTimeField(null=False, default=datetime.datetime.now)

    def __repr__(self):
        return "<RecordingMetadata('%d','%.3f')>" % (self.recording or 0, self.popularity)
