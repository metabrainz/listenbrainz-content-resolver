import json


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
