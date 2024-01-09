import datetime
import os

from troi.patches.lb_radio_classes.tag import LBRadioTagRecordingElement
from troi.patches.lb_radio import LBRadioPatch
from troi.splitter import plist

from lb_content_resolver.tag_search import LocalRecordingSearchByTagService
from lb_content_resolver.artist_search import LocalRecordingSearchByArtistService
from lb_content_resolver.model.database import db
from lb_content_resolver.content_resolver import ContentResolver
import config


class ListenBrainzRadioLocal:
    ''' 
       Generate local playlists against a music collection available via subsonic.
    '''

    # TODO: Make this an argument
    MATCH_THRESHOLD = .8

    def generate(self, mode, prompt):
        """
           Generate a playlist given the mode and prompt.
        """

        patch = LBRadioPatch({"mode": mode, "prompt": prompt, "echo": True, "debug": True, "min_recordings": 1})
        patch.register_service(LocalRecordingSearchByTagService())
        patch.register_service(LocalRecordingSearchByArtistService())

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

    def resolve_playlist(self, match_threshold, playlist):

        recordings = []
        for recording in playlist.playlists[0].recordings:
            if "subsonic_id" in recording.musicbrainz or "filename" in recording.musicbrainz:
                continue

            recordings.append(recording)

        if not recordings:
            return

        return self.resolve_recordings(match_threshold, recordings)

    def resolve_recordings(self, match_threshold, recordings):
        cr = ContentResolver()
        resolved = cr.resolve_playlist(match_threshold, recordings)

        for i, t_recording in enumerate(recordings):
            if resolved[i] is not None:
                if resolved[i]["subsonic_id"] != "":
                    t_recording.musicbrainz["subsonic_id"] = resolved[i]["subsonic_id"]

                if resolved[i]["file_path"] != "":
                    t_recording.musicbrainz["filename"] = resolved[i]["file_path"]

                t_recording.duration = resolved[i]["duration"]
