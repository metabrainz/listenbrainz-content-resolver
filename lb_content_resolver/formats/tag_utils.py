class TagUtils:

    def extract_track_number(track_number):
        if str(track_number).find("/") != -1:
            track_number, dummy = str(track_number).split("/")
        try:
            return_value = int(track_number)
        except ValueError:
            return_value = 0
        return return_value

    def make_artist_string(artist_id):
        """
            Given artist id tag data, return a string from the data.
            Accepts: list, string. If something else is passed, cast to str.
        """
        if isinstance(artist_id, str):
            print("is string")
            return artist_id

        if isinstance(artist_id, list):
            print("is list")
            return ",".join(artist_id)

        print("is other")
        return str(artist_id)
