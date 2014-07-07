#!/usr/bin/python2
import csv
import pprint
import sys
import os
import time
import dbus
import binascii

# Prefer ../ers-node/ers over installed versions
TESTS_PATH = os.path.dirname(os.path.realpath(__file__))
ERS_PATH = os.path.dirname(TESTS_PATH) + '/../ers-node/ers'
sys.path.insert(0, ERS_PATH)

# Same for the datastore
DATASTORE_PATH = os.path.dirname(TESTS_PATH) + '/../src/carquinyol'
sys.path.insert(0, DATASTORE_PATH)

from ers.api import ERS
from carquinyol.metadatastore import MetadataStore

NS = 'urn:ers:meta:predicates:'

# Create a pretty printer for debugging
pp = pprint.PrettyPrinter(indent=2)

def load_journal_dump(journal_name):
    # Load the preview
    encoded_preview = open('data/preview.txt', 'rb').read()
    preview = dbus.ByteArray(binascii.unhexlify(encoded_preview))
    
    # Load the journal data
    entries = []
    header = None
    with open(journal_name, 'rb') as csvfile:
        reader = csv.reader(csvfile, delimiter='*', quotechar='"')
        for row in reader:
            if header == None:
                header = row
            else:
                dictionary = dict(zip(header, row))
                # Fix types
                dictionary['timestamp'] = int(dictionary['timestamp'])
                # Add extra keys
                dictionary['preview'] = preview
                dictionary['checksum'] = "65b4b8579c41bf650e71ae220f34a1b4"
                dictionary['creation_time'] = dictionary['timestamp']
                dictionary['filesize'] = 325
                dictionary['launch-times'] = str(dictionary['timestamp'])
                # Fix a renamed keys
                dictionary['activity'] = dictionary['act']
                del dictionary['act']
                dictionary['icon-color'] = dictionary['icon_color']
                del dictionary['icon_color']
                dictionary['share-scope'] = dictionary['share_scope']
                del dictionary['share_scope']
                # Remove extra keys
                del dictionary['idx']
                entries.append(dictionary)
    # pp.pprint(entries)
    entries = entries
    print "Loaded {} journal entries".format(len(entries))

    return entries

def store_journal_data(journal_entries):
    # Array to store the times
    times = []
    
    # HACK the metadatastore will not clean the DB, we do it for him
    ers = ERS(reset_database=True)
    del ers
    
    # Insert all the entries
    metadatastore = MetadataStore()
    for entry in journal_entries:
        start = time.time()
        metadatastore.store(entry['uid'], entry)
        times.append(time.time()-start)
        
    return times
    
if __name__ == '__main__':
    timings = []
    
    # Load the journal
    journal = load_journal_dump('data/expanded_journal.csv')
    
    # Insert the data many times
    for repeat in range (0,20):
        print 'Round {}'.format(repeat)
        timing = store_journal_data(journal)
        timings.append(timing)
    
    # Save the output
    with open('journal_stats.csv', 'wb') as csvfile:
        writer = csv.writer(csvfile)
        for timing in timings:
            writer.writerow(timing)
    