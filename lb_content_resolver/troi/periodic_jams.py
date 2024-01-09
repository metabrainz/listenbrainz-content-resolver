from lb_content_resolver.lb_radio import ListenBrainzRadioLocal
from lb_content_resolver.troi.patches.periodic_jams import LocalPeriodicJamsPatch


class LocalPeriodicJams(ListenBrainzRadioLocal):
    ''' 
       Generate local playlists against a music collection available via subsonic.
    '''

    # TODO: Make this an argument
    MATCH_THRESHOLD = .8

    def __init__(self, user_name, target):
        ListenBrainzRadioLocal.__init__(self)
        self.user_name = user_name
        self.target = target

    def generate(self):
        """
           Generate a periodic jams playlist
        """

        patch = LocalPeriodicJamsPatch({
            "user_name": self.user_name,
            "echo": True,
            "debug": True,
            "target": self.target,
            "min_recordings": 1
        })

        # Now generate the playlist
        try:
            playlist = patch.generate_playlist()
        except RuntimeError as err:
            print(f"LB Radio generation failed: {err}")
            return None

        if playlist == None:
            print("Your prompt generated an empty playlist.")
            return {"playlist": {"track": []}}

        # Resolve any tracks that have not been resolved to a subsonic_id or a local file
        self.resolve_playlist(self.MATCH_THRESHOLD, playlist)

        return playlist.get_jspf() if playlist is not None else {"playlist": {"track": []}}
