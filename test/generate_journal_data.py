#!/usr/bin/python2
import csv
import pprint
import uuid
import copy
import random
import calendar
from datetime import datetime, timedelta

# The input journal
SEED = 'data/journals_data.csv'

# The output generated
OUTPUT = 'data/expanded_journal.csv'
OUTPUT_SIZE = 1000

# Create a pretty printer for debugging
pp = pprint.PrettyPrinter(indent=2)

def weighted_random_choice(choices):
    '''
    Do a roulette based selection
    code from http://bit.ly/1pTSXIR
    '''
    max = sum(choices.values())
    pick = random.uniform(0, max)
    current = 0
    for key, value in choices.items():
        current += value
        if current > pick:
            return key

def pick_journal_entry(entries):
    '''
    Choose a journal entry to repeat
    '''
    # Group activities by activity name
    activities = {}
    for entry in entries:
        if entry['act'] != 'NA':
            activities.setdefault(entry['act'], []).append(entry)
    
    # Count them
    activities_count = {}
    for (k,v) in activities.iteritems():
        activities_count[k] = len(v)
    
    # Pick an activity name to repeat and then one of the specific instance
    activity_name = weighted_random_choice(activities_count)
    entry = random.choice(activities[activity_name])
    
    # Return a copy of the entry
    return copy.copy(entry)

def go():
    # Load the journal data
    entries = []
    header = None
    with open(SEED, 'rb') as csvfile:
        reader = csv.reader(csvfile, delimiter='*', quotechar='"')
        for row in reader:
            if header == None:
                header = row
            else:
                dictionary = dict(zip(header, row))
                entries.append(dictionary)
    # pp.pprint(entries)
    entries = entries
    print "Loaded {} seed journal entries".format(len(entries))

    while len(entries) != OUTPUT_SIZE:
        # Pick one
        new_entry = pick_journal_entry(entries)
        
        # Give it a new id, index and usage time
        new_entry['uid'] = uuid.uuid1()
        new_entry['idx'] = len(entries)
        in_future = True
        while in_future:
            # Generate a new usage date, just ensure this is not in the future
            date = datetime.strptime(new_entry['mtime'], "%Y-%m-%dT%H:%M:%S.%f")  
            offset = timedelta(days = random.uniform(-360,360), seconds = random.uniform(-2000,2000))
            date = date + offset
            in_future = date > datetime.now()
        new_entry['mtime'] = date.strftime("%Y-%m-%dT%H:%M:%S.%f")
        new_entry['timestamp'] = calendar.timegm(date.utctimetuple())
        
        # Store it
        entries.append(new_entry)
        
    print "Generated {} journal entries".format(len(entries))
    
    # Write the journal data
    with open(OUTPUT, 'wb') as csvfile:
        writer = csv.writer(csvfile, delimiter='*', quotechar='"')
        writer.writerow(header)
        for entry in entries:
            row = [entry[key] for key in header]
            writer.writerow(row)
    
if __name__ == '__main__':
    go()