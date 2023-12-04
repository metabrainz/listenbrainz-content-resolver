import datetime
import os

from troi.patches.lb_radio_classes.tag import LBRadioTagRecordingElement
from troi.patches.lb_radio import LBRadioPatch
from troi.splitter import plist
from lb_content_resolver.tag_search import TagSearch
import config


class LBLocalRadioTagRecordingElement(LBRadioTagRecordingElement):

    def __init__(self, db, tags, operator="and", mode="easy", include_similar_tags=True):
        super().__init__(tags, operator, mode, include_similar_tags)
        self.db = db

    def fetch_tag_data(self, tags, operator, min_subsonic_id=-1):

        # Fetch our mode ranges
        start, stop = self.local_storage["modes"][self.mode]

        ts = TagSearch(self.db)

        recordings = plist()
        for rec in ts.search(tags, operator, start, stop):
            recordings.append({ "recording_mbid": rec[0], "percent": rec[1], "subsonic_id": rec[2] })

        return recordings


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

        # Create the new element and swap it into place
        tag_element = LBLocalRadioTagRecordingElement(self.db, "[no tags]")
        old_elements = patch.exchange_element("LBRadioTagRecordingElement", tag_element)

        # Clearly this shit aint gonna work
        old_element = old_elements[0]

        # Take the initalized values of the old element and copy to new element
        tag_element.tags = old_element.tags
        tag_element.operator = old_element.operator
        tag_element.mode = old_element.mode
        tag_element.include_similar_tags = old_element.include_similar_tags

        # Now generate the playlist
        try:
            playlist = patch.generate_playlist()
        except RuntimeError as err:
            print(f"LB Radio generation failed: {err}")
            return

        return playlist.get_jspf() if playlist is not None else {"playlist": {"tracks": []}}
