import mutagen
import mutagen.flac

from lb_content_resolver.formats.tag_utils import get_tag_value, extract_track_number


def read(file):

    tags = None
    try:
        tags = mutagen.flac.FLAC(file)
    except mutagen.flac.HeaderNotFoundError:
        print("Cannot read metadata from file %s" % file.encode("utf-8"))
        return None

    mdata = {}
    mdata["artist_name"] = get_tag_value(tags, "artist")
    mdata["artist_sortname"] = get_tag_value(tags, "artistsort", mdata["artist_name"])
    mdata["release_name"] = get_tag_value(tags, "album")
    mdata["recording_name"] = get_tag_value(tags, "title")
    mdata["track_num"] = extract_track_number(get_tag_value(tags, "tracknumber"))
    mdata["disc_num"] = int(get_tag_value(tags, "discnumber"))
    mdata["artist_mbid"] = get_tag_value(tags, "musicbrainz_artistid")
    mdata["recording_mbid"] = get_tag_value(tags, "musicbrainz_trackid")
    mdata["release_mbid"] = get_tag_value(tags, "musicbrainz_albumid")
    mdata["duration"] = int(tags.info.length * 1000)

    return mdata
