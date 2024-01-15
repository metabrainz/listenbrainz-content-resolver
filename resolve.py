#!/usr/bin/env python3

import os
import sys

import click

from lb_content_resolver.content_resolver import ContentResolver
from lb_content_resolver.database import Database
from lb_content_resolver.subsonic import SubsonicDatabase
from lb_content_resolver.metadata_lookup import MetadataLookup
from lb_content_resolver.lb_radio import ListenBrainzRadioLocal
from lb_content_resolver.utils import ask_yes_no_question
from lb_content_resolver.top_tags import TopTags
from lb_content_resolver.duplicates import FindDuplicates
from lb_content_resolver.artist_search import LocalRecordingSearchByArtistService
from lb_content_resolver.troi.periodic_jams import LocalPeriodicJams
from lb_content_resolver.playlist import read_jspf_playlist, write_m3u_playlist_from_results, write_m3u_playlist_from_jspf
from lb_content_resolver.unresolved_recording import UnresolvedRecordingTracker
from troi.playlist import PLAYLIST_TRACK_EXTENSION_URI


DEFAULT_CHUNKSIZE = 100


def output_playlist(db, jspf, upload_to_subsonic, save_to_playlist, dont_ask):
    if jspf is None:
        return

    if upload_to_subsonic:
        import config

        if len(jspf["playlist"]["track"]) > 0 and config.SUBSONIC_HOST != "":
            try:
                _ = jspf["playlist"]["track"][0]["extension"][PLAYLIST_TRACK_EXTENSION_URI] \
                        ["additional_metadata"]["subsonic_identifier"]
            except KeyError:
                print("Playlist does not appear to contain subsonic ids. Can't upload to subsonic.")
                return

            if dont_ask or ask_yes_no_question("Upload via subsonic? (Y/n)"):
                print("uploading playlist")
                db.upload_playlist(jspf)

    elif save_to_playlist is not None and len(jspf["playlist"]["track"]) > 0:
        try:
            _ = jspf["playlist"]["track"][0]["location"]
        except KeyError:
            print("Playlist does not appear to contain file paths. Can't write a local playlist.")
            return
        if dont_ask or ask_yes_no_question(f"Save to '{save_to_playlist}'? (Y/n)"):
            print("saving playlist")
            write_m3u_playlist_from_jspf(save_to_playlist, jspf)

    else:
        print("Playlist displayed, but not saved. Use -p or -u options to save/upload playlists.")


def db_file_check(db_file):
    """ Check the db_file argument and give useful user feedback. """

    if not db_file:
        try:
            import config
        except ModuleNotFoundError:
            print("Database file not specified with -d (--db_file) argument. Consider adding it to config.py for ease of use.")
            sys.exit(-1)

        if not config.DATABASE_FILE:
            print("config.py found, but DATABASE_FILE is empty. Please add it or use -d option to specify it.")
            sys.exit(-1)

        return config.DATABASE_FILE
    else:
        return db_file


def music_directories_from_config():
    """ Returns list of music directories if any in config file. """

    try:
        import config
        return list(set(config.MUSIC_DIRECTORIES))
    except:
        return []


@click.group()
def cli():
    pass


@click.command()
@click.option("-d", "--db_file", help="Database file for the local collection", required=False, is_flag=False)
def create(db_file):
    """Create a new database to track a music collection"""
    db_file = db_file_check(db_file)
    db = Database(db_file)
    db.create()


@click.command()
@click.option("-d", "--db_file", help="Database file for the local collection", required=False, is_flag=False)
@click.option('-c', '--chunksize', default=DEFAULT_CHUNKSIZE)
@click.argument('music_dirs', nargs=-1, type=click.Path())
def scan(db_file, music_dirs, chunksize=DEFAULT_CHUNKSIZE):
    """Scan one or more directories and their subdirectories for music files to add to the collection.
       If no path is passed, check for MUSIC_DIRECTORIES in config instead.
    """
    db_file = db_file_check(db_file)
    db = Database(db_file)
    db.open()
    if not music_dirs:
        music_dirs = music_directories_from_config()
    db.scan(music_dirs, chunksize=chunksize)

    # Remove any recordings from the unresolved recordings that may have just been added.
    urt = UnresolvedRecordingTracker()
    releases = urt.cleanup()


@click.command()
@click.option("-d", "--db_file", help="Database file for the local collection", required=False, is_flag=False)
@click.option("-r", "--remove", required=False, is_flag=True, default=True)
def cleanup(db_file, remove):
    """Perform a database cleanup. Check that files exist and if they don't remove from the index"""
    db_file = db_file_check(db_file)
    db = Database(db_file)
    db.open()
    db.database_cleanup(remove)


@click.command()
@click.option("-d", "--db_file", help="Database file for the local collection", required=False, is_flag=False)
def metadata(db_file):
    """Lookup metadata (popularity and tags) for recordings"""
    db_file = db_file_check(db_file)
    db = Database(db_file)
    db.open()
    lookup = MetadataLookup()
    lookup.lookup()

    print("\nThese top tags describe your collection:")
    tt = TopTags()
    tt.print_top_tags_tightly(100)


@click.command()
@click.option("-d", "--db_file", help="Database file for the local collection", required=False, is_flag=False)
def subsonic(db_file):
    """Scan a remote subsonic music collection"""
    db_file = db_file_check(db_file)
    db = SubsonicDatabase(db_file)
    db.open()
    db.sync()


@click.command()
@click.option("-d", "--db_file", help="Database file for the local collection", required=False, is_flag=False)
@click.option('-t', '--threshold', default=.80)
@click.argument('jspf_playlist')
@click.argument('m3u_playlist')
def playlist(db_file, threshold, jspf_playlist, m3u_playlist):
    """ Resolve a JSPF file with MusicBrainz recording MBIDs to files in the local collection"""
    db_file = db_file_check(db_file)
    db = Database(db_file)
    db.open()
    cr = ContentResolver()
    jspf = read_jspf_playlist(jspf_playlist)
    results = cr.resolve_playlist(threshold, jspf_playlist=jspf)
    write_m3u_playlist_from_results(m3u_playlist, jspf["playlist"]["title"], results)


@click.command()
@click.option("-d", "--db_file", help="Database file for the local collection", required=False, is_flag=False)
@click.option('-t', '--threshold', default=.80)
@click.option('-u', '--upload-to-subsonic', required=False, is_flag=True)
@click.option('-p', '--save-to-playlist', required=False)
@click.option('-y', '--dont-ask', required=False, is_flag=True, help="write playlist to m3u file")
@click.argument('mode')
@click.argument('prompt')
def lb_radio(db_file, threshold, upload_to_subsonic, save_to_playlist, dont_ask, mode, prompt):
    """Use the ListenBrainz Radio engine to create a playlist from a prompt, using a local music collection"""
    db_file = db_file_check(db_file)
    db = SubsonicDatabase(db_file)
    db.open()
    r = ListenBrainzRadioLocal()
    jspf = r.generate(mode, prompt, threshold)
    if len(jspf["playlist"]["track"]) == 0:
        print(upload_to_subsonic)
        db.metadata_sanity_check(include_subsonic=upload_to_subsonic)
        return

    output_playlist(db, jspf, upload_to_subsonic, save_to_playlist, dont_ask)


@click.command()
@click.option("-d", "--db_file", help="Database file for the local collection", required=False, is_flag=False)
@click.argument('count', required=False, default=250)
def top_tags(db_file, count):
    "Display the top most used tags in the music collection. Useful for writing LB Radio tag prompts"
    db_file = db_file_check(db_file)
    db = Database(db_file)
    db.open()
    tt = TopTags()
    tt.print_top_tags_tightly(count)


@click.command()
@click.option("-d", "--db_file", help="Database file for the local collection", required=False, is_flag=False)
@click.option('-e', '--exclude-different-release', required=False, default=False, is_flag=True)
@click.option('-v', '--verbose', help="Display extra info about found files", required=False, default=False, is_flag=True)
def duplicates(db_file, exclude_different_release, verbose):
    "Print all the tracks in the DB that are duplicated as per recording_mbid"
    db_file = db_file_check(db_file)
    db = Database(db_file)
    db.open()
    fd = FindDuplicates(db)
    fd.print_duplicate_recordings(exclude_different_release, verbose)


@click.command()
@click.option("-d", "--db_file", help="Database file for the local collection", required=False, is_flag=False)
@click.option('-t', '--threshold', default=.80)
@click.option('-u', '--upload-to-subsonic', required=False, is_flag=True, default=False)
@click.option('-p', '--save-to-playlist', required=False)
@click.option('-y', '--dont-ask', required=False, is_flag=True, help="write playlist to m3u file")
@click.argument('user_name')
def periodic_jams(db_file, threshold, upload_to_subsonic, save_to_playlist, dont_ask, user_name):
    "Generate a periodic jams playlist"
    db_file = db_file_check(db_file)
    db = SubsonicDatabase(db_file)
    db.open()

    target = "subsonic" if upload_to_subsonic else "filesystem"
    pj = LocalPeriodicJams(user_name, target, threshold)
    jspf = pj.generate()
    if len(jspf["playlist"]["track"]) == 0:
        db.metadata_sanity_check(include_subsonic=upload_to_subsonic)
        return

    output_playlist(db, jspf, upload_to_subsonic, save_to_playlist, dont_ask)


@click.command()
@click.option("-d", "--db_file", help="Database file for the local collection", required=False, is_flag=False)
def unresolved(db_file):
    "Show the top unresolved releases"
    db_file = db_file_check(db_file)
    db = Database(db_file)
    db.open()
    urt = UnresolvedRecordingTracker()
    releases = urt.get_releases()
    urt.print_releases(releases)


cli.add_command(create)
cli.add_command(scan)
cli.add_command(playlist)
cli.add_command(cleanup)
cli.add_command(metadata)
cli.add_command(subsonic)
cli.add_command(lb_radio)
cli.add_command(top_tags)
cli.add_command(duplicates)
cli.add_command(periodic_jams)
cli.add_command(unresolved)


def usage(command):
    with click.Context(command) as ctx:
        click.echo(command.get_help(ctx))


if __name__ == "__main__":
    cli()
    sys.exit(0)
