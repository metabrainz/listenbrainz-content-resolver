from peewee import SqliteDatabase

db = SqliteDatabase(None, pragmas=(('foreign_keys', 'on'),))

def setup_db(db_file):
    global db
    db.init(db_file)
