from whoosh.fields import *

schema = Schema(
    file_path=ID(stored=True, unique=True), 
    recording_mbid=ID(stored=True), 
    release_mbid=ID(stored=True), 
    artist_mbid=ID(stored=True),

    recording_name=TEXT(stored=True),
    release_name=TEXT(stored=True), 
    artist_name=TEXT(stored=True), 

    track_num=NUMERIC(stored=True), 
    duration=NUMERIC(stored=True),

    lookup=TEXT(stored=True), 
    lookup_release=TEXT(stored=True), 
)
