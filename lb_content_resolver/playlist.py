import os

import json


def convert_jspf_to_m3u(scanner, jspf_file, m3u_file, distance=2):

    jspf = read_jspf_playlist(jspf_file)

    title = jspf["playlist"]["title"]
    recordings = []
    for track in jspf["playlist"]["track"]:

        mbid = track["identifier"][34:]
        artist = track["creator"]
        recording = track["title"]
        hits = scanner.resolve_recording(artist, recording, distance)
        if hits is None or len(hits) == 0:
            print("recording %s (%s - %s) not resolved." % (mbid[:6], artist[:20], recording[:20]))
            continue

        mdata = hits[0]
        print("recording %s resolved: %s" % (mbid[:6], os.path.basename(mdata["file_path"])))
        recordings.append(mdata)

    generate_m3u_playlist(m3u_file, title, recordings)


def read_jspf_playlist(jspf_file):

    with open(jspf_file, "r") as f:
        js = f.read()

    return json.loads(js)


def generate_m3u_playlist(file_name, playlist_title, recordings):

    with open(file_name, "w") as m3u:
        m3u.write("#EXTM3U\n")
        m3u.write("#EXTENC: UTF-8\n")
        m3u.write("#PLAYLIST %s\n" % playlist_title)
        for rec in recordings:
            m3u.write("#EXTINF %d,%s\n" % (rec["duration"] / 1000, rec["recording_name"]))
            m3u.write(rec["file_path"] + "\n")
