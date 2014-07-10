#!/usr/bin/python3
import csv
import statistics
import matplotlib.pyplot as plt
from scipy.interpolate import interp1d
import numpy

def plot(data_name):
    data = {}
        
    # Load the data
    with open(data_name + '.csv', 'r') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            for i in range(0,len(row)):
                data.setdefault(i,[])
                data[i].append(float(row[i]))
    
    # Compute means
    means = []
    for (t,values) in data.items():
        m = statistics.mean(values)
        d = statistics.pstdev(values)
        means.append(m)

    # Bag the results
    x = [int(round(x)) for x in numpy.logspace(0.1, 3, num=30, endpoint=True)]
    y = []
    for index_x in range(0, len(x)):
        start = x[index_x-1]-1 if index_x > 0 else 0
        end = x[index_x]
        y.append(statistics.mean(means[start:end]))

    # Plot        
    f = interp1d(x, y, kind='cubic')
    fig = plt.figure(figsize=(10, 5))
    plt.xscale('log')
    plt.xlabel('Number of entries in the journal')
    plt.ylabel('Response time in seconds')
    plt.plot(x, y)
    plt.plot(x, y, 'ro')
    plt.savefig(data_name + '.png',dpi=150)
    
if __name__ == '__main__':
    plot('journal_stats_laptop')
    plot('journal_stats_rpi')
    plot('journal_stats')
    
