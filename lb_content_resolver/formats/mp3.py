# -*- coding: utf-8 -*-

import mutagen
import mutagen.mp3

def read(file, mtime):

    mdata = { 'mtime' : mtime }

    tags = None
    try:
        tags = mutagen.mp3.MP3(file)
    except mutagen.mp3.HeaderNotFoundError:
        print("Cannot read metadata from file %s" % file.encode('utf-8'))
        return None

    mdata['duration'] = int(tags.info.length * 1000)
    if 'TPE1' in tags: 
        mdata['artist_name'] = str(tags['TPE1'])
    else:
        mdata['artist_name'] = unknownString

    if 'TSOP' in tags: 
        mdata['sortname'] = str(tags['TSOP'])
    else:
        if 'XSOP' in tags: 
            mdata['artist_sortname'] = str(tags['XSOP'])
        else:
            mdata['artist_sortname'] = ""

    if 'TALB' in tags: 
        mdata['release_name'] = str(tags['TALB'])
    else:
        mdata['release_name'] = unknownString

    if 'TIT2' in tags: 
        mdata['recording_name'] = str(tags['TIT2'])
    else:
        mdata['recording_name'] = unknownString

    if 'TRCK' in tags: 
        mdata['track_num'] = str(tags['TRCK'])
        if str(mdata['track_num']).find('/') != -1: 
            mdata['track_num'], dummy = str(mdata['track_num']).split('/')
        try:
            mdata['track_num'] = int(mdata['track_num'])
        except ValueError:
            mdata['track_num'] = 0
    else:
        mdata['track_num'] = 0

    if 'TXXX:MusicBrainz Artist Id' in tags: 
        id = str(tags['TXXX:MusicBrainz Artist Id'])
        # sometimes artist id fields contain two ids. For now, pick the first one and go
        ids = id.split('/')
        mdata['artist_mbid'] = ids[0]
    else:
        mdata['artist_mbid'] = ''

    if 'UFID:http://musicbrainz.org' in tags: 
        mdata['recording_mbid'] = tags['UFID:http://musicbrainz.org'].data.decode('utf-8')
    else:
        mdata['recording_mbid'] = ''

    if 'TXXX:MusicBrainz Album Id' in tags: 
        mdata['release_mbid'] = str(tags['TXXX:MusicBrainz Album Id'])
    else:
        mdata['release_mbid'] = ''

    if 'TXXX:MusicBrainz Album Artist Id' in tags: 
        mdata['release_artist_mbid'] = str(tags['TXXX:MusicBrainz Album Artist Id'])
    else:
        mdata['release_artist_mbid'] = ''

    return mdata
