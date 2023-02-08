from peewee import *
from lb_content_resolver.model.database import db


class Recording(Model):
    """
    Basic metadata information about a recording on disk (a track).
    """

    class Meta:
        database = db

    id = AutoField()
    path = TextField(null=False, unique=True)
    mtime = TimestampField(null=False)

    artist_name = TextField(null=False)
    release_name = TextField(null=False)
    recording_name = TextField(null=False)

    recording_mbid = UUIDField(index=True)
    artist_mbid = UUIDField(index=True)
    release_mbid = UUIDField(index=True)

    duration = IntegerField(null=True)
    tnum = IntegerField(null=True)

    def __repr__(self):
        return "<Recording('%s','%s')>" % (self.mbid, self.name)
