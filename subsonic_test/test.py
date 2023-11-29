#!/usr/bin/env python3

from pprint import pprint
import libsonic

MAX_ALBUMS_PER_CALL = 500
conn = libsonic.Connection('http://10.1.1.109' , 'mayhem' , 'm!D7XHmVGy@4' , port=4533)

recordings = []
album_count = 0
while True:
    albums_this_batch = 0;
    albums = conn.getAlbumList(ltype="alphabeticalByArtist", size=MAX_ALBUMS_PER_CALL, offset=album_count)
    for album in albums["albumList"]["album"]:
        album_info = conn.getAlbum(id=album["id"])
        for song in album_info["album"]["song"]:
            recordings.append((song["id"], song["path"]))
        album_count += 1
        albums_this_batch += 1

    print(album_count, albums_this_batch)
    if albums_this_batch < MAX_ALBUMS_PER_CALL:
        break

print(f"loaded {len(recordings)} recordings")
