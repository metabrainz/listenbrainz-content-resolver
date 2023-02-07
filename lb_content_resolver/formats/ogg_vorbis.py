# -*- coding: utf-8 -*-

import mutagen
import mutagen.oggvorbis

from lb_content_resolver.formats.tag_utils import TagUtils


def get(tags, tag, default):

    try:
        t = tags[tag]
    except KeyError:
        return default

    return t[0]


def read(file, mtime, unknown_string):
    mdata = { "mtime" : mtime }

    tags = None
    try:
        tags = mutagen.oggvorbis.OggVorbis(file)
    except mutagen.oggvorbis.HeaderNotFoundError:
        print("Cannot read metadata from file %s" % file)
        return None

    mdata["artist_name"] = get(tags, "artist", unknown_string)
    mdata["artist_sortname"] = get(tags, "artistsort", unknown_string)
    mdata["release_name"] = get(tags, "album", unknown_string)
    mdata["recording_name"] = get(tags, "title", unknown_string)
    mdata["track_num"]  = TagUtils.extract_track_number(get(tags, "tracknumber", "0"))

    # TODO: improve how we handle MBIDs, IFF we use a DB, rather than document search. TBD
    mdata["artist_mbid"] = get(tags, "musicbrainz_artistid", "")
    mdata["recording_mbid"] = get(tags, "musicbrainz_releasetrackid", "")
    mdata["release_mbid"] = get(tags, "musicbrainz_albumartistid", "")

    mdata["duration"] = int(tags.info.length * 1000)

    return mdata
