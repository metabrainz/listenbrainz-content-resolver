from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='ListenBrainz Content Resolver',
    version='1.0.0',
    url='https://github.com/metabrainz/listenbrainz-content-resolver.git',
    author='Robert Kaye',
    author_email='rob@metabrainz.org',
    description='A library and command line tool for taking MBID based JSPF playlists and resolving them to a local collection of tracks.',
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
    install_requires=[
        "Click==8.1.3",
        "mutagen==1.46.0",
        "nmslib==2.1.1",
        "regex==2023.6.3",
        "scikit-learn==1.2.1",
        "Unidecode==1.3.6",
    ],
    use_scm_version=True,
    setup_requires=['setuptools_scm'],
)
