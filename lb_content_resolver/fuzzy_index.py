import os
import datetime
import re
import sys

from sklearn.feature_extraction.text import TfidfVectorizer
import nmslib
from unidecode import unidecode


def ngrams(string, n=3):
    """ Take a lookup string (noise removed, lower case, etc) and turn a list of trigrams """

    string = ' '+ string +' ' # pad names for ngrams...
    ngrams = zip(*[string[i:] for i in range(n)])
    return [''.join(ngram) for ngram in ngrams]


class FuzzyIndex:
    ''' 
    '''

    def __init__(self, index_dir):
        self.index_dir = index_dir
        self.lookup_strings = None
        self.lookup_ids = None
        self.vectorizer = None
        self.lookup_matrix = None
        self.index = None

    def create(self):
        try:
            os.mkdir(self.index_dir)
        except OSError as err:
            print("Could not create index directory: %s (%s)" % (self.index_dir, err))
            return

    def open(self):
        """ 
            Open an existing index for searching.
        """

    def save(self):
        """ Save to disk """


    def close(self):
        """ close , flush mem """

    def encode_string(self, text):
        return unidecode(re.sub(" +", " ", re.sub(r'[^\w ]+', '', text)).strip().lower())

    def build_new_index(self, artist_recording_data):
        """
            Builds a new index and saves it to disk and keeps it in ram as well.
        """
        self.lookup_strings = []
        self.lookup_ids = []
        for artist_name, recording_name, lookup_id in artist_recording_data:
            self.lookup_strings.append(self.encode_string(artist_name) + self.encode_string(recording_name))
            self.lookup_ids.append(lookup_id)

        self.vectorizer = TfidfVectorizer(min_df=1, analyzer=ngrams)
        self.lookup_matrix = vectorizer.fit_transform(lookup_strings)

        self.index = nmslib.init(method='simple_invindx', space='negdotprod_sparse_fast', data_type=nmslib.DataType.SPARSE_VECTOR)
        self.index.addDataPointBatch(self.lookup_matrix)
        self.index.createIndex()

    def search(self, artist_recording_data):
        """ 
            Return IDs for the matches in a list. Returns a list of tuples(matched_string, confidence, ID).
            If no match found, row will have tuple with all None values.
        """

        query_strings = []
        for artist_name, recording_name in artist_recording_data:
            self.query_strings.append(self.encode_string(artist_name) + self.encode_string(recording_name))

        query_matrix = self.vectorizer.transform(query_strings)
        results = self.index.knnQueryBatch(query_matrix, k = 1, num_threads = 1)

        output = [] 
        for i, result in enumerate(results):
            output.append((self.lookup_strings[result[0][0]], self.lookup_ids[result[0][0]], result[1][0]))

        return output
