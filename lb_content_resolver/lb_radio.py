import datetime
import os

from troi.patches.lb_radio_classes.tag import LBRadioTagRecordingElement
from troi.patches.lb_radio import LBRadioPatch
from troi.splitter import plist

from lb_content_resolver.tag_search import LocalRecordingSearchByTagService
import config


class ListenBrainzRadioLocal:
    ''' 
       Generate local playlists against a music collection available via subsonic.
    '''

    def __init__(self, db):
        self.db = db

    def generate(self, mode, prompt):
        """
           Generate a playlist given the mode and prompt.
        """

        self.db.open_db()

        patch = LBRadioPatch({"mode": mode, "prompt": prompt, "echo": True, "debug": True, "min_recordings": 1})
        patch.register_service(LocalRecordingSearchByTagService(self.db))

        # Now generate the playlist
        try:
            playlist = patch.generate_playlist()
        except RuntimeError as err:
            print(f"LB Radio generation failed: {err}")
            return

        return playlist.get_jspf() if playlist is not None else {"playlist": {"tracks": []}}
