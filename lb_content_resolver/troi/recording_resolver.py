#from troi.musicbrainz.recording_lookup import RecordingLookupElement
from troi import Element

from lb_content_resolver.content_resolver import ContentResolver
from lb_content_resolver.model.subsonic import RecordingSubsonic
from lb_content_resolver.model.recording import Recording
from troi import Recording


class RecordingResolverElement(Element):

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

        # TODO: Add a check to make sure that metadata is present.

        # Build the fuzzy index
        lookup_data = []
        for recording in inputs[0]:
            lookup_data.append({"artist_name": recording.artist.name, "recording_name": recording.name})

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
