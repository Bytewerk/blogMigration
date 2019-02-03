#!/usr/bin/env python3
# coding: utf-8

import code
import os
import sys
import argparse
import locale
import yaml
from datetime import datetime, timedelta, timezone

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('dir', help='directory to process')
    
    args = parser.parse_args()
    
    blogEntries = []
    
    for entry in os.scandir(args.dir):
        if (not entry.is_file()):
            continue
        if (entry.name == 'authors.yml'):
            continue
        if (not(entry.name.endswith('.yml'))):
            continue
        with open(entry.path, 'r') as f:
            data = yaml.load(f)
        blogEntries.append(data)
    
    archive = {}
    for year in range(2009, 2019):
        archive[year] = {}
        for month in range(1, 13):
            archive[year][month] = []
    
    for entry in blogEntries:
        date = datetime.fromisoformat(entry['date'])
        archive[date.year][date.month].append(entry)
    
    for year in reversed(range(2009, 2019)):
        print(f'Year {year}:')
        for month in reversed(range(1, 13)):
            num = len(archive[year][month])
            if (num):
                print(f'\t{month}: {num}')
    
    for entry in archive[2010][3]:
        print(entry['title'])
    return 0
    
if __name__ == '__main__':
    sys.exit(main())
