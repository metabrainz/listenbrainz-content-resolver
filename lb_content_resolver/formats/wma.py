import mutagen
import mutagen.asf

from lb_content_resolver.formats.tag_utils import get_tag_value, extract_track_number


def read(file):

    tags = None
    try:
        tags = mutagen.asf.ASF(file)
    except mutagen.asf.HeaderNotFoundError:
        print("Cannot read metadata from file %s" % file)
        return None

    mdata = {}
    mdata["artist_name"] = str(get_tag_value(tags, "Author"))
    mdata["artist_sortname"] = str(get_tag_value(tags, "WM/ArtistSortOrde", mdata["artist_name"]))
    mdata["release_name"] = str(get_tag_value(tags, "WM/AlbumTitle"))
    mdata["recording_name"] = str(get_tag_value(tags, "Title"))
    mdata["track_num"] = extract_track_number(str(get_tag_value(tags, "WM/TrackNumber")))
    mdata["artist_mbid"] = str(get_tag_value(tags, "MusicBrainz/Artist Id"))
    mdata["recording_mbid"] = str(get_tag_value(tags, "MusicBrainz/Release Track Id"))
    mdata["release_mbid"] = str(get_tag_value(tags, "MusicBrainz/Album Id") )
    mdata["duration"] = int(tags.info.length * 1000)

    return mdata
