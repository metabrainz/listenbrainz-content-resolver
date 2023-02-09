#!/usr/bin/env python3

import re
from random import randint
from time import time

from sklearn.feature_extraction.text import TfidfVectorizer
import nmslib

TEST_STRINGS = [
        "massiveattackteardropbartclaessentomfallbootleg",
        "squirrelnutzippersivefoundanewbaby",
        "giantsand1helvakowboysong",
        "ericserrathepantryhideout",
        "bobdylanalabamagetaway",
        "bobdylanleopardskinpillboxhatincomplete",
        "thereplacementsyouaintgottadancestudiodemo",
        "steviewonderijustcalledtosayiloveyou",
        "thestonerosesmadeofstone808statemix",
        "yolatengotomcourtenayacousticversion",
]

def fuck_string_up(text, num_chars_to_remove):

    for i in range(num_chars_to_remove):
        remove = randint(0, len(text))
        text = text[:remove] + text[remove+1:]

    return text 

def ngrams(string, n=3):
    """ Take a lookup string (noise removed, lower case, etc) and turn a list of trigrams """

    string = ' '+ string +' ' # pad names for ngrams...
    ngrams = zip(*[string[i:] for i in range(n)])
    return [''.join(ngram) for ngram in ngrams]

def load_sample_data():

    data = []
    with open("content-resolver-test-data.txt", "r") as txt:
        while True:
            line = txt.readline()
            if not line:
                break

            line = line.strip()
            data.append(line)

    return data

M = 80
efC = 1000
K=1
num_threads = 4
num_chars_to_remove = 5

print("load sample data")
data = load_sample_data()

query_data = []
for text in TEST_STRINGS:
    query_data.append(fuck_string_up(text, num_chars_to_remove))

print("Vectorize")
vectorizer = TfidfVectorizer(min_df=1, analyzer=ngrams)
tf_idf_matrix = vectorizer.fit_transform(data)


print("Create index")
index = nmslib.init(method='simple_invindx', space='negdotprod_sparse_fast', data_type=nmslib.DataType.SPARSE_VECTOR) 
index.addDataPointBatch(tf_idf_matrix)
index.createIndex()

print("match items")
t0 = time()
messy_tf_idf_matrix = vectorizer.transform(query_data)
query_qty = messy_tf_idf_matrix.shape[0]
nbrs = index.knnQueryBatch(messy_tf_idf_matrix, k = K, num_threads = 1) #num_threads)
t1 = time()

print("query time: %.3fs (%.3fms per item)" % (t1 - t0, (t1 - t0) * 1000 / len(TEST_STRINGS)))

for i in range(len(nbrs)):
  original_nm = query_data[i]
  correct_nm = TEST_STRINGS[i]
  try:
    matched_nm   = data[nbrs[i][0][0]]
    conf         = nbrs[i][1][0]
  except:
    matched_nm   = "no match found"
    conf         = None
  if correct_nm != matched_nm:
      print(" BAD: %-50s -> %-50s %.3f" % (original_nm, matched_nm, conf))
  else:
      print("GOOD: %-50s -> %-50s %.3f" % (original_nm, matched_nm, conf))
