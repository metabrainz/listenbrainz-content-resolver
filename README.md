# Introduction

The ListenBrainz Content Resolver resolves global JSPF playlists to
a local collection of music, using the resolve function.

ListenBrainz Local Radio allows you to generate tag radio playlists that
can be uploaded to your favorite subsonic API enabled music system.

## Quick Start

To install the package:

```
python -m venv .virtualenv
source .virtualenv/bin/activate
pip install -r requirements.txt
```

## Scanning your collection

Then prepare the index and scan a music collection. mp3, m4a, wma, OggVorbis, OggOpus and flac files are supported.

```
./resolve.py create music_index
./resolve.py scan music_index <path to mp3/flac files>
```

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
./resolve.py playlist music_index input.jspf output.m3u
```

Then open the m3u playlist with a local tool.

## Create playlists with ListenBrainz Local Radio

### Prerequisites

NOTE: This feature only works if you music collection 
is tagged with MusicBrainz tags. (We recommend Picard:
http://picard.musicbrainz.org ) and if your music
collection is also available via a Subsonic API.

### Setup

In order to use the LB Local Radio playlist generator you'll need
to download more data for your MusicBrainz tagged music collection.

First, download tag and popularity data:

```
./resolve.py metadata music_index
```

Then, copy config.py.sample to config.py and then edit config.py:

```
cp config.py.sample config.py
edit config.py
```

Fill out the values for your subsonic server API and save the file.
Finally, match your collection against the subsonic collection:

```
./resolve.py subsonic music_index
```

### Playlist generation

Currently only tag elements are supported for LB Local Radio.

To generate a playlist:

```
./resolve.py lb-radio music_index easy 'tag:(downtempo, trip hop)'
```

This will generate a playlist on easy mode for recordings that are
tagged with "downtempo" AND "trip hop".

```
./resolve.py lb-radio music_index medium 'tag:(downtempo, trip hop)::or'
```

This will generate a playlist on medium mode for recordings that are
tagged with "downtempo" OR "trip hop", since the or option was specified
at the end of the prompt.

You can include more than on tag query in a prompt:

```
./resolve.py lb-radio music_index medium 'tag:(downtempo, trip hop)::or tag:(punk, ska)'
```
