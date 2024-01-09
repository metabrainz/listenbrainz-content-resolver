from troi import Element

from lb_content_resolver.content_resolver import ContentResolver
from lb_content_resolver.model.subsonic import RecordingSubsonic
from lb_content_resolver.model.recording import Recording
from lb_content_resolver.model.database import db
from troi import Recording


class RecordingResolverElement(Element):
    """
        This Troi element takes in a list of recordings, which *must* have artist name and recording
        name set and resolves them to a local collection by using the ContentResolver class
    """

    def __init__(self, match_threshold, target="filesystem"):
        """ Match threshold: The value from 0 to 1.0 on how sure a match must be to be accepted.
            target: Either "filesystem" or "subsonic", the audio file source we're working with.
        """
        Element.__init__(self)
        self.match_threshold = match_threshold
        self.resolve = ContentResolver()
        self.target = target

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
        recording_ids = tuple([result["recording_id"] for result in resolved])

        # Could also be done with: 
        # Recording.select().join(RecordingSubsonic, JOIN.LEFT_OUTER).where(Recording.id.in_(recording_ids))

        # Fetch the recordings to lookup subsonic ids
        query = """SELECT recording.id
                        , file_path
                        , subsonic_id
                     FROM recording
                LEFT JOIN recording_subsonic
                       ON recording_subsonic.recording_id = recording.id
                    WHERE """

        where_clause_elements = []
        for id in recording_ids:
            where_clause_elements.append("recording.id = %d" % id)
            
        where_clause = " or ".join(where_clause_elements)
        query += where_clause

        cursor = db.execute_sql(query)
        recordings = []
        for row in cursor.fetchall():
            recordings.append({ "recording_id": row[0],
                                "file_path": row[1],
                                "subsonic_id": row[2] })

        # Build a indexes
        subsonic_index = {}
        file_index = {}
        for recording in recordings:
            if "subsonic_id" in recording:
                subsonic_index[recording["recording_id"]] = recording["subsonic_id"]
            if "file_path" in recording:
                file_index[recording["recording_id"]] = recording["file_path"]

        # Set the ids into the recordings and only return recordings with an ID, depending on target
        results = []
        for r in resolved:
            recording = inputs[0][r["index"]]
            if self.target == "subsonic":
                try:
                    recording.musicbrainz["subsonic_id"] = subsonic_index[r["recording_id"]]
                except KeyError:
                    continue

                results.append(recording)

            if self.target == "filesystem":
                try:
                    recording.musicbrainz["filename"] = file_index[r["recording_id"]]
                except KeyError:
                    continue

                results.append(recording)

        return results
