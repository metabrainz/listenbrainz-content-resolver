import os
import datetime
from math import fabs
from time import time
import re
import sys

from sklearn.feature_extraction.text import TfidfVectorizer
import nmslib
from unidecode import unidecode


def ngrams(string, n=3):
    """ Take a lookup string (noise removed, lower case, etc) and turn into a list of trigrams """

    string = ' ' + string + ' '  # pad names for ngrams...
    ngrams = zip(*[string[i:] for i in range(n)])
    return [''.join(ngram) for ngram in ngrams]


class FuzzyIndex:
    ''' 
       Create a fuzzy index using a Term Frequency, Inverse Document Frequency (tf-idf)
       algorithm. Currently the libraries that implement this cannot be serialized to disk,
       so this is an in memory operation. Fortunately for our amounts of data, it should
       be quick to rebuild this index.
    '''

    def __init__(self, index_dir):
        self.index_dir = index_dir
        self.vectorizer = None
        self.index = None

    def create(self):
        try:
            os.mkdir(self.index_dir)
        except OSError as err:
            print("Could not create index directory: %s (%s)" % (self.index_dir, err))
            return

    def encode_string(self, text):
        if text is None:
            return None
        return unidecode(re.sub(" +", "", re.sub(r'[^\w ]+', '', text)).strip().lower())

    def build(self, artist_recording_data):
        """
            Builds a new index and saves it to disk and keeps it in ram as well.
        """
        self.lookup_strings = []
        lookup_ids = []
        for artist_name, recording_name, lookup_id in artist_recording_data:
            if artist_name is None or recording_name is None:
                continue
            self.lookup_strings.append(self.encode_string(artist_name) + self.encode_string(recording_name))
            lookup_ids.append(lookup_id)

        t0 = time()
        self.vectorizer = TfidfVectorizer(min_df=1, analyzer=ngrams)
        lookup_matrix = self.vectorizer.fit_transform(self.lookup_strings)
        t1 = time()
        print(f"  build index in ram: %.3fs" % (t1 - t0))

        self.index = nmslib.init(method='simple_invindx', space='negdotprod_sparse_fast', data_type=nmslib.DataType.SPARSE_VECTOR)
        self.index.addDataPointBatch(lookup_matrix, lookup_ids)
        self.index.createIndex()

    def search(self, artist_recording_data, match_threshold):
        """ 
            Return IDs for the matches in a list. Returns a list of tuples(matched_string, confidence, ID).
            If no match found, row will have tuple with all None values.
        """

        query_strings = []
        for artist_name, recording_name in artist_recording_data:
            if artist_name is None or recording_name is None:
                continue

            query_strings.append(self.encode_string(artist_name) + self.encode_string(recording_name))

        t0 = time()
        query_matrix = self.vectorizer.transform(query_strings)
        t1 = time()
        print(f"  build query in ram: %.3fs" % (t1 - t0))
        t0 = time()
        results = self.index.knnQueryBatch(query_matrix, k=1, num_threads=1)
        t1 = time()
        print(f"      execute search: %.3fs" % (t1 - t0))

        # hack, remove
        import psutil
        process = psutil.Process(os.getpid())
        used = int(process.memory_info().rss / 1024 / 1024)
        print(f" MB ram used (final): {used:,}\n")

        output = []
        for i, result in enumerate(results):
            if result[0][0] is None or fabs(result[1][0]) < match_threshold:
                output.append((None, None, result[1][0]))
            else:
                output.append((self.lookup_strings[result[0][0]], result[0][0], result[1][0]))

        return output
