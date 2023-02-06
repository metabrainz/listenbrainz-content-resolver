# -*- coding: utf-8 -*-
#!/usr/bin/python

import os
import sys
import db
import artist

from pysqlite2 import dbapi2 as sqlite

# TODO: Make cleanup optional, rather than blasting everything away.
#       break database cleanup into smaller bits
#       stop using the lists and just check everything in the DB

def makeUnique(list):
    u = {}
    for x in list: u[x] = 1
    return u.keys()

def databaseCleanup(file):
    '''
    Look for missing tracks and remove them from the DB. Then look for empty releases/artists and remove those too
    '''

    dbc = db.DB(file)

    checkReleases = []
    checkArtists = []

    cur = dbc.cursor()
    rows = []

    print "Checking tracks"
    try:
        cur.execute("select track.id, location, release, artist from track, release_join where release_join.track = track.id order by track.id")
        rows = cur.fetchall()
    except sqlite.OperationalError, msg:
        print "Cannot get list of tracks: %s" % msg
        sys.exit(-1)

    for id, path, release, artistid in rows:
        if os.path.exists(path): continue

        print "track %s is missing" % path
        try:
            cur.execute("delete from track where id = ?", (id,))
            cur.execute("delete from release_join where track = ?", (id,))
            dbc.commit()
        except sqlite.OperationalError, msg:
            dbc.rollback()
            print "Cannot delete tracks: %s" % msg
            sys.exit(-1)

        checkArtists.append(artistid)
        checkReleases.append(release)

    print "Checking releases"
    for releaseid in makeUnique(checkReleases):
        rows = []
        try:
            cur.execute("select count(*) from release_join where release = ?", (releaseid,))
            rows = cur.fetchall()
        except sqlite.OperationalError, msg:
            print "Cannot get list of releases: %s" % msg
            sys.exit(-1)

        if rows[0][0] == 0:
            print "release %s has no tracks" % releaseid
            try:
                cur.execute("delete from release where id = ?", (releaseid,))
                dbc.commit()
            except sqlite.OperationalError, msg:
                dbc.rollback()
                print "Cannot delete release: %s" % msg
                sys.exit(-1)

    print "Checking artists"
    for artistid in makeUnique(checkArtists):
        if artistid == artist.VARTIST_ID: continue
        rows = []
        try:
            cur.execute("select count(*) from release where artist = ?", (artistid,))
            rows = cur.fetchall()
        except sqlite.OperationalError, msg:
            print "Cannot get list of releases by artist %d:: %s" % (artistid, msg)
            sys.exit(-1)

        if rows[0][0] == 0:
            rows = []
            try:
                cur.execute("select count(*) from track where artist = ?", (artistid,))
                rows = cur.fetchall()
            except sqlite.OperationalError, msg:
                print "Cannot get list of tracks by artist %d:: %s" % (artistid, msg)
                sys.exit(-1)

            if rows[0][0] == 0:
                print "artist %s has no tracks or releases" % artistid
                try:
                    cur.execute("delete from artist where id = ?", (artistid,))
                    dbc.commit()
                except sqlite.OperationalError, msg:
                    dbc.rollback()
                    print "Cannot delete artist: %s" % msg
                    sys.exit(-1)


def usage():
    print "Usage: %s: <database file>" % sys.argv[0]
    sys.exit(-1)

def run():
    # Parse the command line args
    opts = None
    args = None
    try:
        opts, args = getopt.getopt(sys.argv[1:], "")
    except:
        usage()

    if not len(args): usage()

    databaseCleanup(args[0])
    sys.exit(0)
