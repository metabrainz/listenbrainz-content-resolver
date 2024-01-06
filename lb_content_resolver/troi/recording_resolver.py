from troi import Element

from lb_content_resolver.content_resolver import ContentResolver
from lb_content_resolver.model.subsonic import RecordingSubsonic
from lb_content_resolver.model.recording import Recording
from troi import Recording


class RecordingResolverElement(Element):
    """
        This Troi element takes in a list of recordings, which *must* have artist name and recording
        name set and resolves them to a local collection by using the ContentResolver class
    """

    def __init__(self, db, match_threshold):
        Element.__init__(self)
        self.db = db
        self.match_threshold = match_threshold
        self.resolve = ContentResolver(db)

    @staticmethod
    def inputs():
        return []

    @staticmethod
    def outputs():
        return [Recording]

    def read(self, inputs):

        # Build the fuzzy index
        lookup_data = []
        for recording in inputs[0]:
            if recording.artist is None or recording.artist.name is None or recording.name is None:
                raise RuntimeError("artist name and recording name are needed for RecordingResolverElement.")

            lookup_data.append({"artist_name": recording.artist.name,
                                "recording_name": recording.name,
                                "recording_mbid": recording.mbid})

        self.resolve.build_index()

        # Resolve the recordings
        resolved = self.resolve.resolve_recordings(lookup_data, self.match_threshold)
        recording_ids = [result["recording_id"] for result in resolved]

        # Fetch the recordings to lookup subsonic ids
        recordings = RecordingSubsonic \
                      .select() \
                      .where(RecordingSubsonic.recording_id.in_(recording_ids)) \
                      .dicts()

        # Build a subsonic index
        subsonic_index = {}
        matched = []
        for recording in recordings:
            matched.append(recording["recording"])
            subsonic_index[recording["recording"]] = recording["subsonic_id"]

        # Set the subsonic ids into the recordings and only return recordings with an ID
        results = []
        for r in resolved:
            try:
                recording = inputs[0][r["index"]]
                recording.musicbrainz["subsonic_id"] = subsonic_index[r["recording_id"]]
            except KeyError:
                continue

            results.append(recording)

        return results
