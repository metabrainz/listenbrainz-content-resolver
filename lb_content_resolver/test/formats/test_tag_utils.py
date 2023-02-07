from lb_content_resolver.formats.tag_utils import TagUtils


class TestTagUtils:

    def test_int(self):
        assert TagUtils.extract_track_number(100) == 100
        assert TagUtils.extract_track_number(-100) == -100

    def test_string(self):
        assert TagUtils.extract_track_number("100") == 100

    def test_string_with_slash(self):
        assert TagUtils.extract_track_number("9/12") == 9

    def test_invalid_values(self):
        assert TagUtils.extract_track_number("") == 0
        assert TagUtils.extract_track_number("NotANumber") == 0
        assert TagUtils.extract_track_number("3.0") == 0
