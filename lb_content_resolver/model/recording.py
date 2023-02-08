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

    recording_mbid = UUIDField(null=True, index=True)
    artist_mbid = UUIDField(null=True, index=True)
    release_mbid = UUIDField(null=True, index=True)

    duration = IntegerField()
    track_num = IntegerField()

    def __repr__(self):
        return "<Recording('%s','%s')>" % (self.mbid, self.name)
