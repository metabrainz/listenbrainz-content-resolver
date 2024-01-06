#!/usr/bin/env python3

import os

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
import config

# TODO: Make sure all functions work with subsonic and with local files
# TODO: avoid passing in db to objects and just open the db


def output_playlist(db, jspf, upload_to_subsonic, save_to_playlist, dont_ask):
    if jspf is None:
        return

    if upload_to_subsonic and len(jspf["playlist"]["track"]) > 0 and config.SUBSONIC_HOST != "":
        if dont_ask or ask_yes_no_question("Upload via subsonic? (Y/n)"):
            print("uploading playlist")
            db.upload_playlist(jspf)
    elif save_to_playlist is not None and len(jspf["playlist"]["track"]) > 0:
        if dont_ask or ask_yes_no_question(f"Save to '{save_to_playlist}'? (Y/n)"):
            print("saving playlist")
            write_m3u_playlist_from_jspf(save_to_playlist, jspf)

    else:
        print("Playlist displayed, but not saved. Use -p or -u options to save/upload playlists.")


@click.group()
def cli():
    pass


@click.command()
@click.argument('index_dir')
def create(index_dir):
    """Create a new index directory to track a music collection"""
    db = Database(index_dir)
    db.create()


@click.command()
@click.argument('index_dir')
@click.argument('music_dir')
def scan(index_dir, music_dir):
    """Scan a directory and its subdirectories for music files to add to the collection"""
    db = Database(index_dir)
    db.scan(music_dir)


@click.command()
@click.argument('index_dir')
def cleanup(index_dir):
    """Perform a database cleanup. Check that files exist and if they don't remove from the index"""
    db = Database(index_dir)
    db.database_cleanup()


@click.command()
@click.argument('index_dir')
def metadata(index_dir):
    """Lookup metadata (popularity and tags) for recordings"""
    db = Database(index_dir)
    lookup = MetadataLookup(db)
    lookup.lookup()

    print("\nThese top tags describe your collection:")
    tt = TopTags(db)
    tt.print_top_tags_tightly(100)


@click.command()
@click.argument('index_dir')
def subsonic(index_dir):
    """Scan a remote subsonic music collection"""
    db = SubsonicDatabase(index_dir)
    db.sync()


@click.command()
@click.argument('index_dir')
@click.argument('jspf_playlist')
@click.argument('m3u_playlist')
@click.option('-t', '--threshold', default=.80)
def playlist(index_dir, jspf_playlist, m3u_playlist, threshold):
    """ Resolve a JSPF file with MusicBrainz recording MBIDs to files in the local collection"""
    db = Database(index_dir)
    cr = ContentResolver(db)
    jspf = read_jspf_playlist(jspf_playlist)
    results = cr.resolve_playlist(threshold, jspf_playlist=jspf)
    write_m3u_playlist_from_results(m3u_playlist, jspf["playlist"]["title"], results)


@click.command()
@click.option('-u', '--upload-to-subsonic', required=False, is_flag=True)
@click.option('-p', '--save-to-playlist', required=False)
@click.option('-y', '--dont-ask', required=False, is_flag=True, help="write playlist to m3u file")
@click.argument('index_dir')
@click.argument('mode')
@click.argument('prompt')
def lb_radio(upload_to_subsonic, save_to_playlist, dont_ask, index_dir, mode, prompt):
    """Use the ListenBrainz Radio engine to create a playlist from a prompt, using a local music collection"""
    db = SubsonicDatabase(index_dir)
    r = ListenBrainzRadioLocal(db)
    jspf = r.generate(mode, prompt)
    output_playlist(db, jspf, upload_to_subsonic, save_to_playlist, dont_ask)


@click.command()
@click.argument('index_dir')
@click.argument('count', required=False, default=250)
def top_tags(index_dir, count):
    "Display the top most used tags in the music collection. Useful for writing LB Radio tag prompts" ""
    db = Database(index_dir)
    tt = TopTags(db)
    tt.print_top_tags_tightly(count)


@click.command()
@click.argument('index_dir')
@click.option('-e', '--exclude-different-release', required=False, default=False, is_flag=True)
def duplicates(exclude_different_release, index_dir):
    "Print all the tracks in the DB that are duplciated as per recording_mbid" ""
    db = Database(index_dir)
    fd = FindDuplicates(db)
    fd.print_duplicate_recordings(exclude_different_release)


@click.command()
@click.option('-u', '--upload-to-subsonic', required=False, is_flag=True)
@click.option('-p', '--save-to-playlist', required=False)
@click.option('-y', '--dont-ask', required=False, is_flag=True, help="write playlist to m3u file")
@click.argument('index_dir')
@click.argument('user_name')
def periodic_jams(upload_to_subsonic, save_to_playlist, dont_ask, index_dir, user_name):
    "Generate a periodic jams playlist"
    db = SubsonicDatabase(index_dir)
    pj = LocalPeriodicJams(db, user_name)
    jspf = pj.generate()
    output_playlist(db, jspf, upload_to_subsonic, save_to_playlist, dont_ask)

@click.command()
@click.option('-c', '--count', required=False, default=25)
@click.option('-l', '--lookup-count', required=False, default=3)
@click.argument('index_dir')
def unresolved_releases(count, lookup_count, index_dir):
    "Show the top unresolved releases"

    db = SubsonicDatabase(index_dir)
    db.open_db()
    urt = UnresolvedRecordingTracker()
    releases = urt.get_releases(num_items=count, lookup_count=lookup_count)
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
cli.add_command(unresolved_releases)


def usage(command):
    with click.Context(command) as ctx:
        click.echo(command.get_help(ctx))


if __name__ == "__main__":
    cli()
    sys.exit(0)
