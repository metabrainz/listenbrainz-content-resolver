import mutagen
import mutagen.oggopus

from lb_content_resolver.formats.tag_utils import get_tag_value, extract_track_number


def read(file):

    tags = None
    try:
        tags = mutagen.oggopus.OggOpus(file)
    except mutagen.oggous.HeaderNotFoundError:
        print("Cannot read metadata from file %s" % file)
        return None

    mdata = {}
    mdata["artist_name"] = get_tag_value(tags, "artist")
    mdata["artist_sortname"] = get_tag_value(tags, "artistsort")
    mdata["release_name"] = get_tag_value(tags, "album")
    mdata["recording_name"] = get_tag_value(tags, "title")
    mdata["track_num"] = extract_track_number(get_tag_value(tags, "tracknumber"))
    mdata["artist_mbid"] = get_tag_value(tags, "musicbrainz_artistid", "")
    mdata["recording_mbid"] = get_tag_value(tags, "musicbrainz_releasetrackid", "")
    mdata["release_mbid"] = get_tag_value(tags, "musicbrainz_albumartistid", "")
    mdata["duration"] = int(tags.info.length * 1000)

    return mdata
