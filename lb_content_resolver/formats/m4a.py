from uuid import UUID 

import mutagen
import mutagen.mp4

from lb_content_resolver.formats.tag_utils import get_tag_value, extract_track_number


def read(file):

    tags = None
    try:
        tags = mutagen.mp4.MP4(file)
    except mutagen.mp4.HeaderNotFoundError:
        print("Cannot read metadata from file %s" % file)
        return None

    mdata = {}
    mdata["artist_name"] = get_tag_value(tags, "©ART")
    mdata["artist_sortname"] = get_tag_value(tags, "soar", mdata["artist_name"])
    mdata["release_name"] = get_tag_value(tags, "©alb")
    mdata["recording_name"] = get_tag_value(tags, "©nam")
    mdata["track_num"] = extract_track_number(get_tag_value(tags, "trkn"))
    mdata["artist_mbid"] = get_tag_value(tags, "----:com.apple.iTunes:MusicBrainz Artist Id").decode("utf-8")
    mdata["recording_mbid"] = get_tag_value(tags, "----:com.apple.iTunes:MusicBrainz Track Id").decode("utf-8")
    mdata["release_mbid"] = get_tag_value(tags, "----:com.apple.iTunes:MusicBrainz Album Id").decode("utf-8")
    mdata["duration"] = int(tags.info.length * 1000)

    return mdata
