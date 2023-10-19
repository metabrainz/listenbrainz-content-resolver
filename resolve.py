#!/usr/bin/env python3

import os
from lb_content_resolver.content_resolver import ContentResolver
from lb_content_resolver.database import Database
from lb_content_resolver.metadata_lookup import MetadataLookup
import click


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
def lookup(index_dir):
    db = Database(index_dir)
    lookup = MetadataLookup(db)
    lookup.lookup()


@click.command()
@click.argument('index_dir')
@click.argument('jspf_playlist')
@click.argument('m3u_playlist')
@click.option('-t', '--threshold', default=.80)
def playlist(index_dir, jspf_playlist, m3u_playlist, threshold):
    db = Database(index_dir)
    cr = ContentResolver(db)
    cr.resolve_playlist(jspf_playlist, m3u_playlist, threshold)


cli.add_command(create)
cli.add_command(scan)
cli.add_command(playlist)
cli.add_command(cleanup)
cli.add_command(lookup)


def usage(command):
    with click.Context(command) as ctx:
        click.echo(command.get_help(ctx))


if __name__ == "__main__":
    cli()
    sys.exit(0)
