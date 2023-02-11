# Introduction

Soon we'll need to write a content resolver. Soon was probably over 15 years ago,
so this a bit overdue. :)

## Quick Start

To install the package:

```
python -m venv .virtualenv
source .virtualenv/bin/activate
pip install -r requirements.txt
```

Then prepare the index and scan a music collection. mp3 and flac are supported.

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


## Current limitations / open questions

The Whoosh library that was being used for fuzzy indexing seems to be buggy and unsupported.
After much searching I found another approach, using this method:

  https://towardsdatascience.com/fuzzy-matching-at-scale-84f2bfd0c536

These work very well and are *very* fast. However, the libraries lack the ability to seralize
these indexes to disk, which annoying. But that can be worked around if we decide to use this
approach. 

How things work now:

1. Scan files and save data into a sqlite database.
2. When resolving a playlist or a recording, the metadata is loaded from sqlite and the indexes are built.
3. Then the resolving happens.

So far this isn't a problem and it may not be -- given that 500,000 recordings get indexed in a few seconds.
and if this has to be done once at startup of a services, it might be ok.

Open question: Do we want to continue working with this approach? Are the scikit.learn and nmslib ok
to include as depedencies?
