#!/usr/bin/env python3

import os
import sys

import click

from lb_content_resolver.content_resolver import ContentResolver
from lb_content_resolver.database import Database
from lb_content_resolver.model.recording import FileIdType
from lb_content_resolver.subsonic import SubsonicDatabase
from lb_content_resolver.metadata_lookup import MetadataLookup
from lb_content_resolver.lb_radio import ListenBrainzRadioLocal
from lb_content_resolver.utils import ask_yes_no_question
from lb_content_resolver.top_tags import TopTags
from lb_content_resolver.duplicates import FindDuplicates
from lb_content_resolver.artist_search import LocalRecordingSearchByArtistService
from lb_content_resolver.troi.periodic_jams import LocalPeriodicJams
from lb_content_resolver.playlist import read_jspf_playlist, write_m3u_playlist, write_jspf_playlist
from lb_content_resolver.unresolved_recording import UnresolvedRecordingTracker
from troi.playlist import PLAYLIST_TRACK_EXTENSION_URI

try:
    import config
except ImportError:
    config = None


DEFAULT_CHUNKSIZE = 100


def output_playlist(db, playlist, upload_to_subsonic, save_to_m3u, save_to_jspf, dont_ask):
    try:
        recording = playlist.playlists[0].recordings[0]
    except (KeyError, IndexError):
        print("Cannot save empty playlist.")
        return

    if upload_to_subsonic and config:
        if recording and config.SUBSONIC_HOST:
            try:
                _ = recording.musicbrainz["subsonic_id"]
            except KeyError:
                print("Playlist does not appear to contain subsonic ids. Can't upload to subsonic.")
                return

            if dont_ask or ask_yes_no_question("Upload via subsonic? (Y/n)"):
                print("uploading playlist")
                db.upload_playlist(playlist)
            return

    try:
        _ = recording.musicbrainz["filename"]
    except KeyError:
        print("Playlist does not appear to contain file paths. Can't write a local playlist.")
        return

    if save_to_m3u:
        if dont_ask or ask_yes_no_question(f"Save to '{save_to_m3u}'? (Y/n)"):
            print("saving playlist")
            write_m3u_playlist(save_to_m3u, playlist)
        return

    if save_to_jspf:
        if dont_ask or ask_yes_no_question(f"Save to '{save_to_jspf}'? (Y/n)"):
            print("saving playlist")
            write_jspf_playlist(save_to_jspf, playlist)
        return

    print("Playlist displayed, but not saved. Use -p or -u options to save/upload playlists.")


def db_file_check(db_file):
    """ Check the db_file argument and give useful user feedback. """

    if not db_file:
        if not config:
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
        return list(set(config.MUSIC_DIRECTORIES))
    except AttributeError:
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
@click.option('-c', '--chunksize', default=DEFAULT_CHUNKSIZE, help="Number of files to add/update at once")
@click.option("-f", "--force", required=False, is_flag=True, default=False, help="Force scanning, ignoring any cache")
@click.argument('music_dirs', nargs=-1, type=click.Path())
def scan(db_file, music_dirs, chunksize=DEFAULT_CHUNKSIZE, force=False):
    """Scan one or more directories and their subdirectories for music files to add to the collection.
       If no path is passed, check for MUSIC_DIRECTORIES in config instead.
    """
    db_file = db_file_check(db_file)
    db = Database(db_file)
    db.open()
    if not music_dirs:
        music_dirs = music_directories_from_config()
    db.scan(music_dirs, chunksize=chunksize, force=force)

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
    db = SubsonicDatabase(db_file, config)
    db.open()
    db.sync()


@click.command()
@click.option("-d", "--db_file", help="Database file for the local collection", required=False, is_flag=False)
@click.option('-t', '--threshold', default=.80)
@click.option('-u', '--upload-to-subsonic', required=False, is_flag=True)
@click.option('-m', '--save-to-m3u', required=False)
@click.option('-j', '--save-to-jspf', required=False)
@click.option('-y', '--dont-ask', required=False, is_flag=True, help="write playlist to m3u file")
@click.argument('jspf_playlist')
def playlist(db_file, threshold, upload_to_subsonic, save_to_m3u, save_to_jspf, dont_ask, jspf_playlist):
    """ Resolve a JSPF file with MusicBrainz recording MBIDs to files in the local collection"""
    db_file = db_file_check(db_file)
    db = SubsonicDatabase(db_file, config)
    db.open()
    lbrl = ListenBrainzRadioLocal()
    playlist = read_jspf_playlist(jspf_playlist)
    lbrl.resolve_playlist(threshold, playlist)
    output_playlist(db, playlist, upload_to_subsonic, save_to_m3u, save_to_jspf, dont_ask)


@click.command()
@click.option("-d", "--db_file", help="Database file for the local collection", required=False, is_flag=False)
@click.option('-t', '--threshold', default=.80)
@click.option('-u', '--upload-to-subsonic', required=False, is_flag=True)
@click.option('-m', '--save-to-m3u', required=False)
@click.option('-j', '--save-to-jspf', required=False)
@click.option('-y', '--dont-ask', required=False, is_flag=True, help="write playlist to m3u file")
@click.argument('mode')
@click.argument('prompt')
def lb_radio(db_file, threshold, upload_to_subsonic, save_to_m3u, save_to_jspf, dont_ask, mode, prompt):
    """Use the ListenBrainz Radio engine to create a playlist from a prompt, using a local music collection"""
    db_file = db_file_check(db_file)
    db = SubsonicDatabase(db_file, config)
    db.open()
    r = ListenBrainzRadioLocal()
    playlist = r.generate(mode, prompt, threshold)
    try:
        _ = playlist.playlists[0].recordings[0]
    except (KeyError, IndexError):
        db.metadata_sanity_check(include_subsonic=upload_to_subsonic)
        return

    output_playlist(db, playlist, upload_to_subsonic, save_to_m3u, save_to_jspf, dont_ask)


@click.command()
@click.option("-d", "--db_file", help="Database file for the local collection", required=False, is_flag=False)
@click.option('-t', '--threshold', default=.80)
@click.option('-u', '--upload-to-subsonic', required=False, is_flag=True, default=False)
@click.option('-m', '--save-to-m3u', required=False)
@click.option('-j', '--save-to-jspf', required=False)
@click.option('-y', '--dont-ask', required=False, is_flag=True, help="write playlist to m3u file")
@click.argument('user_name')
def periodic_jams(db_file, threshold, upload_to_subsonic, save_to_m3u, save_to_jspf, dont_ask, user_name):
    "Generate a periodic jams playlist"
    db_file = db_file_check(db_file)
    db = SubsonicDatabase(db_file, config)
    db.open()

    pj = LocalPeriodicJams(user_name, threshold)
    playlist = pj.generate()
    try:
        _ = playlist.playlists[0].recordings[0]
    except (KeyError, IndexError):
        db.metadata_sanity_check(include_subsonic=upload_to_subsonic)
        return

    output_playlist(db, playlist, upload_to_subsonic, save_to_m3u, save_to_jspf, dont_ask)


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
