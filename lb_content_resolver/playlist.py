import json


def read_jspf_playlist(jspf_file):
    """ 
        Read a JSPF playlist from disk.
    """

    with open(jspf_file, "r") as f:
        js = f.read()

    return json.loads(js)


def write_m3u_playlist_from_results(file_name, playlist_title, hits):
    """
       Given a list of Recordings, write an m3u playlist.
    """

    with open(file_name, "w") as m3u:
        m3u.write("#EXTM3U\n")
        m3u.write("#EXTENC: UTF-8\n")
        m3u.write("#PLAYLIST %s\n" % playlist_title)
        for rec in hits:
            if rec is None:
                continue
            m3u.write("#EXTINF %d,%s\n" % (rec["duration"] / 1000, rec["recording_name"]))
            m3u.write(rec["file_path"] + "\n")


def write_m3u_playlist_from_jspf(file_name, jspf):
    """
       Given a jspf playlist, write an m3u playlist.
    """

    with open(file_name, "w") as m3u:
        m3u.write("#EXTM3U\n")
        m3u.write("#EXTENC: UTF-8\n")
        m3u.write("#PLAYLIST %s\n" % jspf["playlist"]["title"])
        for track in jspf["playlist"]["track"]:
            if "location" not in track:
                continue

            m3u.write("#EXTINF %d,%s\n" % (track["duration"] / 1000, track["title"]))
            m3u.write(track["location"] + "\n")
