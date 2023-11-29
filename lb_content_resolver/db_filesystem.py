import os

from lb_content_resolver.database import Database


class FilesystemDatabase(Database):
    ''' 
    Keep a database with metadata for a collection of local music files.
    '''

    def __init__(self, index_dir):
        self.index_dir = index_dir
        self.db_file = os.path.join(index_dir, "lb_resolve.db")
        self.fuzzy_index = None

    def scan(self, music_dir):
        """
            Scan a music dir and add tracks to sqlite.
        """
        self.music_dir = os.path.abspath(music_dir)

        # Keep some stats
        self.total = 0
        self.not_changed = 0
        self.updated = 0
        self.added = 0
        self.error = 0
        self.skipped = 0

        self.open_db()
        self.traverse("")
        self.close_db()

        print("Checked %s tracks:" % self.total)
        print("  %5d tracks not changed since last run" % self.not_changed)
        print("  %5d tracks added" % self.added)
        print("  %5d tracks updated" % self.updated)
        print("  %5d tracks could not be read" % self.error)
        if self.total != self.not_changed + self.updated + self.added + self.error:
            print("And for some reason these numbers don't add up to the total number of tracks. Hmmm.")

    def traverse(self, relative_path):
        """
            This recursive function searches for audio files and descends into sub directories 
        """

        if not relative_path:
            fullpath = self.music_dir
        else:
            fullpath = os.path.join(self.music_dir, relative_path)

        for f in os.listdir(fullpath):
            if f in ['.', '..'] or f.lower().endswith("jpg"):
                continue

            new_relative_path = os.path.join(relative_path, f)
            new_full_path = os.path.join(self.music_dir, new_relative_path)
            if os.path.isfile(new_full_path):
                self.add(new_relative_path)
            if os.path.isdir(new_full_path):
                if not self.traverse(new_relative_path):
                    return False

        return True
