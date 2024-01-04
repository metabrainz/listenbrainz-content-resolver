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

    def __init__(self, db):
        self.db = db

    def sanity_check(self):
        """
        Run a sanity check on the DB to see if data is missing that is required for LB Radio to work.
        """

        self.db.open_db()

        num_recordings = db.execute_sql("SELECT COUNT(*) FROM recording").fetchone()[0]
        num_metadata = db.execute_sql("SELECT COUNT(*) FROM recording_metadata").fetchone()[0]
        num_subsonic = db.execute_sql("SELECT COUNT(*) FROM recording_subsonic").fetchone()[0]

        if num_metadata == 0:
            print("sanity check: You have not downloaded metadata for your collection. Run the metadata command.")
        elif num_metadata < num_recordings // 2:
            print("sanity check: Only %d of your %d recordings have metadata information available. Run the metdata command." %
                  (num_metadata, num_recordings))

        if num_subsonic == 0:
            print(
                "sanity check: You have not matched your collection against the collection in subsonic. Run the subsonic command.")
        elif num_subsonic < num_recordings // 2:
            print("sanity check: Only %d of your %d recordings have subsonic matches. Run the subsonic command." %
                  (num_subsonic, num_recordings))

    def generate(self, mode, prompt):
        """
           Generate a playlist given the mode and prompt.
        """

        self.db.open_db()

        patch = LBRadioPatch({"mode": mode, "prompt": prompt, "echo": True, "debug": True, "min_recordings": 1})
        patch.register_service(LocalRecordingSearchByTagService(self.db))
        patch.register_service(LocalRecordingSearchByArtistService(self.db))

        # Now generate the playlist
        try:
            playlist = patch.generate_playlist()
        except RuntimeError as err:
            print(f"LB Radio generation failed: {err}")
            return None

        if playlist == None:
            print("Your prompt generated an empty playlist.")
            self.sanity_check()

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
        cr = ContentResolver(self.db)
        resolved = cr.resolve_playlist(match_threshold, recordings)

        for i, t_recording in enumerate(recordings):
            if resolved[i] is not None:
                if resolved[i]["subsonic_id"] != "":
                    t_recording.musicbrainz["subsonic_id"] = resolved[i]["subsonic_id"]

                if resolved[i]["file_path"] != "":
                    t_recording.musicbrainz["filename"] = resolved[i]["file_path"]

                t_recording.duration = resolved[i]["duration"]
