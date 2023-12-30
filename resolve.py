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
from lb_content_resolver.artist_search import LocalRecordingSearchByArtistService
from lb_content_resolver.playlist import write_m3u_playlist
import config



@click.group()
def cli():
    pass


@click.command()
@click.argument('index_dir')
def create(index_dir):
    db = Database(index_dir)
    db.create()


@click.command()
@click.argument('index_dir')
@click.argument('music_dir')
def scan(index_dir, music_dir):
    db = Database(index_dir)
    db.scan(music_dir)


@click.command()
@click.argument('index_dir')
def cleanup(index_dir):
    db = Database(index_dir)
    db.database_cleanup()


@click.command()
@click.argument('index_dir')
def metadata(index_dir):
    db = Database(index_dir)
    lookup = MetadataLookup(db)
    lookup.lookup()


@click.command()
@click.argument('index_dir')
def subsonic(index_dir):
    db = SubsonicDatabase(index_dir)
    db.sync()

@click.command()
@click.argument('index_dir')
@click.argument('jspf_playlist')
@click.argument('m3u_playlist')
@click.option('-t', '--threshold', default=.80)
def playlist(index_dir, jspf_playlist, m3u_playlist, threshold):
    db = Database(index_dir)
    cr = ContentResolver(db)
    title, recordings = cr.resolve_playlist(jspf_playlist, threshold)
    cr.resolve_playlist(jspf_playlist, m3u_playlist, threshold)
    write_m3u_playlist(write_m3u_playlist, title, recordings)

@click.command()
@click.option('-u', '--upload-to-subsonic', required=False, is_flag=True)
@click.argument('index_dir')
@click.argument('mode')
@click.argument('prompt')
def lb_radio(upload_to_subsonic, index_dir, mode, prompt):
    db = SubsonicDatabase(index_dir)
    r = ListenBrainzRadioLocal(db)
    jspf = r.generate(mode, prompt)

    if upload_to_subsonic and len(jspf["playlist"]["track"]) > 0 and config.SUBSONIC_HOST != "":
        if ask_yes_no_question("Upload via subsonic? (Y/n)"):
            print("uploading playlist")
            db.upload_playlist(jspf)

@click.command()
@click.argument('index_dir')
@click.argument('count', required=False, default=250)
def top_tags(index_dir, count):
    db = Database(index_dir)
    tt = TopTags(db)
    tt.print_top_tags_tightly(count)


@click.command()
@click.argument('index_dir')
def artist_test(index_dir):
    db = Database(index_dir)
    s = LocalRecordingSearchByArtistService(db)
    s.search(["8f6bd1e4-fbe1-4f50-aa9b-94c450ec0f11", "067102ea-9519-4622-9077-57ca4164cfbb"], .9, .6, 20)
    
cli.add_command(create)
cli.add_command(scan)
cli.add_command(playlist)
cli.add_command(cleanup)
cli.add_command(metadata)
cli.add_command(subsonic)
cli.add_command(lb_radio)
cli.add_command(top_tags)
cli.add_command(artist_test)


def usage(command):
    with click.Context(command) as ctx:
        click.echo(command.get_help(ctx))


if __name__ == "__main__":
    cli()
    sys.exit(0)
