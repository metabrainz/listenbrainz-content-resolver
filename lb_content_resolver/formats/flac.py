# -*- coding: utf-8 -*-

import mutagen
import mutagen.flac

unknown_str = "[unknown]"

def get(tags, tag, default):

    try:
        t = tags[tag]
    except KeyError:
        return default

    return t[0]


def read(file, mtime):
    mdata = { 'mtime' : mtime }

    tags = None
    try:
        tags = mutagen.flac.FLAC(file)
    except mutagen.flac.HeaderNotFoundError:
        print("Cannot read metadata from file %s" % file.encode('utf-8'))
        return None

    mdata['duration'] = int(tags.info.length * 1000)
    mdata['artist_name'] = get(tags, 'artist', unknown_str)
    mdata['artist_sortname'] = get(tags, 'artistsort', mdata['artist_name'])
    mdata['release_name'] = get(tags, 'album', unknown_str)
    mdata['recording_name'] = get(tags, 'title', unknown_str)
    mdata['track_num'] = int(get(tags, 'tracknumber', "0"))
    mdata['artist_mbid'] = get(tags, 'musicbrainz_artistid', "")
    mdata['recording_mbid'] = get(tags, 'musicbrainz_releasetrackid', "")
    mdata['release_mbid'] = get(tags, 'musicbrainz_albumartistid', "")

    return mdata
