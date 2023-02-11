import os
import json

from lb_content_resolver.model.recording import Recording


def convert_jspf_to_m3u(index, jspf_file, m3u_file, distance=2):
    """ 
        Given the lookup index and a JSPF file, resolve tracks and write the m3u file.
    """

    jspf = read_jspf_playlist(jspf_file)

    title = jspf["playlist"]["title"]
    recordings = []
    artist_recording_data = []
    for track in jspf["playlist"]["track"]:
        artist = track["creator"]
        recording = track["title"]
        artist_recording_data.append((track["creator"], track["title"]))

    hits = index.search(artist_recording_data)
    recording_ids = [ r[1] for r in hits ]

    recordings = Recording.select().where(Recording.id.in_(recording_ids))
    rec_index = { r.id : r for r in recordings } 

    # TODO: Improve this overall matching, using releases first, then without. Also 
    # Use other tricks like duration to find the best matches
    results = []
    for hit in hits:
        if hit[0] is None:
            print("recording %s (%s - %s) not resolved." % (mbid[:6], artist[:20], recording[:20]))
            continue

        rec = rec_index[hit[1]]
        print("recording %s resolved: %s" % (rec.recording_name, os.path.basename(rec.file_path)))
        results.append(rec)

    generate_m3u_playlist(m3u_file, title, recordings)


def read_jspf_playlist(jspf_file):
    """ 
        Read a JSPF playlist from disk.
    """

    with open(jspf_file, "r") as f:
        js = f.read()

    return json.loads(js)


def generate_m3u_playlist(file_name, playlist_title, recordings):
    """
       Given a list of Recording objects, write a m3u playlist.
    """

    with open(file_name, "w") as m3u:
        m3u.write("#EXTM3U\n")
        m3u.write("#EXTENC: UTF-8\n")
        m3u.write("#PLAYLIST %s\n" % playlist_title)
        for rec in recordings:
            m3u.write("#EXTINF %d,%s\n" % (rec.duration / 1000, rec.recording_name))
            m3u.write(rec.file_path + "\n")
