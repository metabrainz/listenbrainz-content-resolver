# Introduction

The ListenBrainz Content Resolver resolves global JSPF playlists to
a local collection of music, using the resolve function.

The features of this package include:

1. ListenBrainz Radio Local: allows you to generate radio-style playlists that
that are created using only the files in the local collection, or if that is not
possible, a global playlist with MBIDS will be resolved to a local file collection
as best as possible.

2. Periodic-jams: ListenBrainz periodic-jams, but fully resolved against your own
local collection. This is optimized for local and gives better results than
the global troi patch by the same name.

3. Metadata fetchgin: Several of the features here require metadata to be downloaded
from ListenBrainz in order to power the LB Radio Local.

4. Scan local file collections. MP3, Ogg Vorbis, Ogg Opus, WMA, M4A and FLAC file are supported.

5. Scan a remote subsonic API collection. We've tested Navidrome, Funkwhale and Gonic.

6. Print a report of duplicate files in the collection

7. Print a list of top tags for the collection

8. Print a list of tracks that failed to resolve and print the list of albums that they
belong to. This gives the user feedback about tracks that could be added to the collection
to improve the local matching.


## Installation

To install the package:

```
python -m venv .virtualenv
source .virtualenv/bin/activate
pip install -r requirements.txt
```

### Setting up config.py

While it isn't strictly necessary to setup config.py, it makes using the resolver easier:

```
cp config.py.sample config.py
```

Then edit config.py and set the location of where you're going to store your resolver database file
into DATABASE_FILE. If you plan to use a Subsonic API, the fill out the Subsonic section as well.

If you decide not to use the config.py file, make sure to pass the path to the DB file with -d to each
command. All further examples in this file assume you added the config file and will therefore omit
the -d option.

## Scanning your collection

Note: Soon we will eliminate the requirement to do a filesystem scan before also doing a subsonic
scan (if you plan to use subsonic). For now, do the file system scan, then the subsonic scan.

### Scan a collection on the local filesystem

Then prepare the index and scan a music collection. mp3, m4a, wma, OggVorbis, OggOpus and flac files are supported.

```
./resolve.py create
./resolve.py scan <path to mp3/flac files>
```

If you remove from tracks from your collection, use cleanup to remove refereces to those tracks:

```
./resolve.py cleanup
```

### Scan a Subsonic collection

To enable support you need to create a config.py file config.py.sample:

```
cp config.py.sample config.py
```

Then edit the file and add your subsonic configuration.

```
./resolve.py subsonic
```

This will match your collection to the remove subsonic API collection.


## Resolve JSPF playlists to local collection

Then make a JSPF playlist on LB:

```
https://listenbrainz.org/user/{your username}/playlists/
```

Then download the JSPF file (make sure the playlist is public):

```
curl "https://api.listenbrainz.org/1/playlist/<playlist MBID>" > test.jspf
```

Finally, resolve the playlist to local files:

```
./resolve.py playlist input.jspf output.m3u
```

Then open the m3u playlist with a local tool.

## Create playlists with ListenBrainz Local Radio

### Prerequisites

NOTE: This feature only works if you music collection 
is tagged with MusicBrainz tags. We recommend Picard:
http://picard.musicbrainz.org for tagging your collection.

If you're unwilling to properly tag your collection,
then please do not contact us to request that we remove
this requirement. We can't. We won't. Please close this 
tab and move on.

If you have your collection hosted on an app like Funkwhale,
Navidrom or Gonic, who have a Subsonic API, you can generate
playlists directly the web application.

### Setup

In order to use the LB Local Radio playlist generator you'll need
to download more data for your MusicBrainz tagged music collection.

First, download tag and popularity data:

```
./resolve.py metadata
```

### Playlist generation

Currently artist and tag elements are supported for LB Local Radio,
which means that playlists from these two elements are made from the local 
collection and thus will not need to be resolved. All other elements
may generate playlists with tracks that are not availalble in your
collection. In this case, the fuzzy search will attempt to make the
missing tracks to your collection.

For a complete reference to LB Radio, see:
[ListenBrainz Radio Docs](https://troi.readthedocs.io/en/latest/lb_radio.html)

The playlist generator works with a given mode: "easy", "medium"
and "hard". An easy playlist will generate data that more closely
meets the prompt, which should translate into a playlist that should
be easier and pleasent to listen to. Medium goes further and includes
less popular and more far flung stuff, before hard digs at the bottom
of the barrel. 

This may not always feel very pronounced, especially if your collection
isn't very suited for the prompt that was given.


#### Artist Element

```
./resolve.py lb-radio easy 'artist:(taylor swift, drake)'
```

Generates a playlist with music from Taylor Swift and artists similar
to her and Drake, and artists similar to him.


#### Tag Element

```
./resolve.py lb-radio easy 'tag:(downtempo, trip hop)'
```

This will generate a playlist on easy mode for recordings that are
tagged with "downtempo" AND "trip hop".

```
./resolve.py lb-radio medium 'tag:(downtempo, trip hop)::or'
```

This will generate a playlist on medium mode for recordings that are
tagged with "downtempo" OR "trip hop", since the or option was specified
at the end of the prompt.

You can include more than on tag query in a prompt:

```
./resolve.py lb-radio medium 'tag:(downtempo, trip hop)::or tag:(punk, ska)'
```

#### Stats, Collections, Playlists and Rec

There are more elements, but these are "global" elements that will need to 
have their results resolved to the local collection. The resolution process is
always a bit tricky since its outcome heavily depends on the collection. The
generator will do its best to generate a fitting playlist, but that doesn't
always happen. 

For the other elements, please refer to the 
[ListenBrainz Radio Docs](https://troi.readthedocs.io/en/latest/lb_radio.html)

## Other features

### Collection deduplication

The "duplicates" command will print a report of duplicate recordings
in your collection, based on MusicBrainz Recording MBIDs. There are several
types of duplicates that this may find:

1. Duplicated tracks with the same title, release and artist.
2. Duplicated tracks that live on different releases, but have the same name
3. Duplicated tracks that exist once on an album and again on a compilation.

If you specify -e or --exclude-different-release, then case #3 will not be shown.

### Top tags

The top-tags command will print the top tags and the number of times they
have been used in your collection. This requires that the "metadata"
command was run before.

### Unresolved Releases

Any tracks that fail to resolve to a local collection will have their
recording_mbid saved in the database. This enables the unresolved releases
report which specifies a list of releases that you might consider adding to your
collection, because in the past they failed to resolve to your location collection.

