from setuptools import setup, find_packages

setup(
    name='ListenBrainz Content Resolver',
    version='1.0.0',
    url='https://github.com/metabrainz/listenbrainz-content-resolver.git',
    author='Robert Kaye',
    author_email='rob@metabrainz.org',
    description='A library and command line tool for taking MBID based JSPF playlists and resolving them to a local collection of tracks.',
    packages=find_packages()    
)
