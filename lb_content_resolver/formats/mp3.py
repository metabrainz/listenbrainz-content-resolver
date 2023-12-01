import mutagen
import mutagen.mp3

from lb_content_resolver.formats.tag_utils import get_tag_value, extract_track_number


def read(file):

    tags = None
    try:
        tags = mutagen.mp3.MP3(file)
    except mutagen.mp3.HeaderNotFoundError:
        print("Cannot read metadata from file %s" % file.encode("utf-8"))
        return None

    mdata = {}
    if "TPE1" in tags:
        mdata["artist_name"] = str(tags["TPE1"])
    else:
        mdata["artist_name"] = None

    if "TSOP" in tags:
        mdata["sortname"] = str(tags["TSOP"])
    else:
        if "XSOP" in tags:
            mdata["artist_sortname"] = str(tags["XSOP"])
        else:
            mdata["artist_sortname"] = ""

    if "TALB" in tags:
        mdata["release_name"] = str(tags["TALB"])
    else:
        mdata["release_name"] = None

    if "TIT2" in tags:
        mdata["recording_name"] = str(tags["TIT2"])
    else:
        mdata["recording_name"] = None

    if "TRCK" in tags:
        mdata["track_num"] = extract_track_number(str(tags["TRCK"]))
    else:
        mdata["track_num"] = 0

    if "TPOS" in tags:
        mdata["track_num"] = int(tags["TPOS"])
    else:
        mdata["track_num"] = 0

    if "TXXX:MusicBrainz Artist Id" in tags:
        id = str(tags["TXXX:MusicBrainz Artist Id"])
        # sometimes artist id fields contain two ids. For now, pick the first one and go
        ids = id.split("/")
        mdata["artist_mbid"] = ids[0]
    else:
        mdata["artist_mbid"] = None

    if "UFID:http://musicbrainz.org" in tags:
        mdata["recording_mbid"] = tags["UFID:http://musicbrainz.org"].data.decode("utf-8")
    else:
        mdata["recording_mbid"] = None

    if "TXXX:MusicBrainz Album Id" in tags:
        mdata["release_mbid"] = str(tags["TXXX:MusicBrainz Album Id"])
    else:
        mdata["release_mbid"] = None

    if "TXXX:MusicBrainz Album Artist Id" in tags:
        mdata["release_artist_mbid"] = str(tags["TXXX:MusicBrainz Album Artist Id"])
    else:
        mdata["release_artist_mbid"] = None
    mdata["duration"] = int(tags.info.length * 1000)

    return mdata
