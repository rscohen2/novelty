# Calculate precocity

# This is based on previous calculate-kld scripts,
# but revised in 2023 to address a different
# research question as we evaluate different methods
# of measuring innovation.

# USAGE

# python calculate_prec.py metapath datapath excludepath startdate enddate function

# where

# startdate is inclusive
# enddate exclusive
# and function is either cosine or kld

import pandas as pd
import numpy as np
import random, sys, os
from multiprocessing import Pool
import calc_precocity_worker as cpw
from ast import literal_eval

metapath = sys.argv[1]
datapath = sys.argv[2]
excludepath = sys.argv[3]
startdate = int(sys.argv[4])
enddate = int(sys.argv[5])
function_string = sys.argv[6]

def get_metadata(filepath):
    '''
    Loads the metadata spreadsheet and applies literal_eval to the
    authors column.
    '''
    meta = pd.read_csv(filepath, sep = '\t')
    meta['authors'] = meta['authors'].apply(literal_eval)
    
    return meta

meta = get_metadata(metapath)  # converts the author strings to lists
data = dict()
exclusions = dict()

with open(excludepath, encoding = "utf-8") as f:
    for line in f:
        fields = line.strip().split('\t')
        centerdoc = fields[0]
        if centerdoc not in exclusions:
            exclusions[centerdoc] = []
        for field in fields[1:]:
            exclusions[centerdoc].append(field)

with open(datapath, encoding = "utf-8") as f:
    for line in f:
        fields = line.strip().split('\t')
        chunkid = fields[0]
        vector = np.array([float(x) for x in fields[1:]], dtype = np.float64)
        data[chunkid] = vector

totalvols = meta.shape[0]

spanstocalculate = []
for centerdate in range(startdate, enddate):
    df = meta.loc[(meta.year >= centerdate - 20) & (meta.year <= centerdate + 20) &
    (~pd.isnull(meta.paperId)), : ]
    df.set_index('paperId', inplace = True)
    spanstocalculate.append((centerdate, df))

outputname = 'precocity_' + function_string + '_' + str(startdate)
summaryfile = 'results/' + outputname + 's_docs.tsv'
print(outputname)

# segments = []
# increment = ((endposition - startposition) // numthreads) + 1
# for floor in range(startposition, endposition, increment):
#     ceiling = floor + increment
#     if ceiling > endposition:
#         ceiling = endposition
#     segments.append((floor, ceiling))

packages = []
for centerdate, spanmeta in spanstocalculate:
    spandata = dict()
    spanexclude = dict()
    for paperId, row in spanmeta.iterrows():  # the index is paperId
        for i in range(1000):
            chunkid = paperId + '-' + str(i)
            if i > 990:
                print('danger: ', i)
            if chunkid in data:
                spandata[chunkid] = data[chunkid]
            else:
                break
        if row.year == centerdate and paperId in exclusions:
            spanexclude[paperId] = exclusions[paperId]


    package = (centerdate, spanmeta, spandata, spanexclude, function_string)
    packages.append(package)

del data, meta, exclusions

print('Beginning multiprocessing.')
pool = Pool(processes = len(spanstocalculate))

res = pool.map_async(cpw.calculate_a_year, packages)
res.wait()
resultlist = res.get()
pool.close()
pool.join()
print('Multiprocessing concluded.')

for result in resultlist:
    doc_precocities, centerdate, condition_package = result
    fractions2check, filter_states, positive_radii, aggregates2check = condition_package

    if not os.path.isfile(summaryfile):
        with open(summaryfile, mode = 'w', encoding = 'utf-8') as f:
            outlist = ['docid', 'date', 'num_chunks', 'fraction_compared' 'filtered', 'time_radius', 'chunks_used', 'precocity', 'novelty', 'transience']
            header = '\t'.join(outlist) + '\n'
            f.write(header)

    with open(summaryfile, mode = 'a', encoding = 'utf-8') as f:
        for docid, doc_prec in doc_precocities.items():
            num_chunks = doc_prec['num_chunks']
            for frac in fractions2check:
                for filtered in filter_states:
                    for radius in positive_radii:
                        for aggregate in aggregates2check:
                            prec, nov, trans = doc_prec[(frac, filtered, radius, aggregate)]
                            outline = '\t'.join([str(x) for x in [docid, centerdate, num_chunks, frac, filtered, radius, aggregate, prec, nov, trans]])
                            f.write(outline + '\n')

    print(centerdate, 'written.')



