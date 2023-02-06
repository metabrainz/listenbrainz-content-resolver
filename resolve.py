#!/usr/bin/env python3

import os
from lb_content_resolver.content_resolver import ContentResolver
import click

@click.group()
def cli():
    pass

@click.command()
@click.argument('index_dir')
def create(index_dir):
    sc = ContentResolver(index_dir)
    sc.create()

@click.command()
@click.argument('index_dir')
@click.argument('music_dir')
def scan(index_dir, music_dir):
    sc = ContentResolver(index_dir)
    sc.scan(music_dir)


@click.command()
@click.argument('index_dir')
@click.argument('artist_name')
@click.argument('recording_name')
def track(index_dir, artist_name, recording_name):
    sc = ContentResolver(index_dir)
    sc.resolve_recording(artist_name, recording_name)

@click.command()
@click.argument('index_dir')
@click.argument('jspf_playlist')
@click.argument('m3u_playlist')
def playlist(index_dir, jspf_playlist, m3u_playlist):
    sc = ContentResolver(index_dir)
    sc.resolve_playlist(jspf_playlist, m3u_playlist)

cli.add_command(create)
cli.add_command(scan)
cli.add_command(track)
cli.add_command(playlist)

def usage(command):
    with click.Context(command) as ctx:
        click.echo(command.get_help(ctx))


if __name__ == "__main__":
    cli()
    sys.exit(0)
