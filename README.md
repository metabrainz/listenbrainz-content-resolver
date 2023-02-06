# Introduction

Soon we'll need to write a content resolver. Soon was probably over 15 years ago,
so this a bit overdue. :)

## Quick Start

```
python -m venv .virtualenv
source .virtualenv/bin/activate
pip install -r requirements.txt
```

Then prepare the index:

```
./resolve.py create test_index
./resolve.py scan test_index <path to mp3/flac files>
```

Then make a JSPF playlist on LB:

```
https://listenbrainz.org/user/{your username}/playlists/
```

Then download the JSPF file:

```
curl "https://api.listenbrainz.org/1/playlist/<playlist MBID>" > test.jspf
```

Finally, resolve the playlist to local files:

```
./resolve.py playlist <input JSPF file> <output m3u file>
```

Then open the m3u playlist with a local tool.


## Known problems

Unfortunately the Whoosh full text search (with fuzzy search) is no longer
maintained and has some serious bugs. A better version does not seem to 
exist -- we can examine Xapian, but in previous testing it didn't work
very well for searching data (rather than documents). 

Indexing and searching a collection works. But the search for an existing
record does not work, so when a collection is re-scanned the documents are
added to the index again.


