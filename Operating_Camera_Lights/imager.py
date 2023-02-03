#!/usr/bin/env python3

"""
---IMAGER (v2.0.0)---
Author/Maintainer: Stevan Zorich (zoric002@umn.edu)
PI: Katie Greenham (greenham@umn.edu)
Year: 2021

Integrates with micro-manager using the pycromanager library to take time-series images at
constant intervals starting and ending at a scheduled date/time.

Requires Python 3.6 or greater to run.
"""

__author__ = "Stevan Zorich"
__copyright__ = "Copyright 2021, Greenham Lab"
__version__ = "2.0.0"


import argparse
import time
import threading
import sys
import os
import uuid
from datetime import datetime
from pathlib import Path
from PIL import Image
from pycromanager import Acquisition


# CONSTANTS
# DT_FMT -- expected date/time format for input
# INTERVAL -- expected time interval format for input
# FILE_FMT -- expected date/time format for image filenames
DT_FMT = '%m/%d/%Y %H:%M:%S'
INTERVAL_FMT = '%H:%M:%S'
FILE_FMT = '%Y-%m-%d_%H%M%S'


# FUNCTION dtstr_to_epoch(s, fmt)
# Takes a date/time string and format (in LOCAL time) and returns a UNIX epoch.
def dtstr_to_epoch(s, fmt):
    dt = datetime.strptime(s, fmt)
    return dt.timestamp()


# FUNCTION tstr_to_interval(s, fmt)
# Takes a time string and format and returns the number of seconds in that time interval.
def tstr_to_interval(s, fmt):
    timestruct = time.strptime(s, fmt)
    return timestruct.tm_hour * 3600 + timestruct.tm_min * 60 + timestruct.tm_sec


# FUNCTION build_schedule
# Builds an array of UNIX epochs at equal intervals between two given UNIX epochs
def build_schedule(start, interval, stop):
    sched = []
    cur = start
    while cur <= stop:
        sched.append(cur)
        cur += interval
    return sched


# FUNCTION build_parser()
# Returns argument parser for this program (see Python argparse documentation)
def build_parser():
    parser = argparse.ArgumentParser(epilog='Version 2.0.0')
    parser.add_argument('start', type=str, help='Starting date/time (24-hour, MM/DD/YYYY HH:MM:SS)')
    parser.add_argument('end', type=str, help='Ending date/time (24-hour, MM/DD/YYYY HH:MM:SS)')
    parser.add_argument('interval', type=str, help='Interval between acquisitions (HH:MM:SS)')
    parser.add_argument('-o', '--out', type=str, 
                        help='Output directory (default current directory)', default='./')
    parser.add_argument('-e', '--exposure', type=int,
                        help='Exposure time in milliseconds (exposure set in micro-manager if not specified)',
                        default=None)
    return parser


# FUNCTION image_process_fn(image, metadata, export_path, err_path)
# Callback fn for the imaging routine -- takes image and saves it. Pycromanager expects a
# function that takes two parameters: the image itself, and the metadata in a dict.
# 
# The last two arguments are paths for the image to be written to. If the function cannot
# write to export_path, it will write to err_path. Both of these parameters must be filled using
# a lambda before passing it to pycromanager.
def img_process_fn(image, metadata, export_path, err_path):
    img = Image.fromarray(image)
    imgidx = metadata['Axes']['idx']
    dt = datetime.fromtimestamp(metadata['Axes']['timestamp'])
    timestr = dt.strftime(FILE_FMT)
    imname = f'{timestr}_img_{imgidx:04}.tif'
    try:
        img.save(os.path.join(export_path, imname))
    except FileNotFoundError:
        if not os.path.exists(err_path):
            os.mkdir(err_path)
        img.save(os.path.join(err_path, imname))
        print('ERROR: Could not write to directory', export_path, '; saved backup to', err_path)


# MAIN SUBROUTINE
if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    outdir = args.out
   
    start_time = dtstr_to_epoch(args.start, DT_FMT)
    interval = tstr_to_interval(args.interval, INTERVAL_FMT)
    end_time = dtstr_to_epoch(args.end, DT_FMT)
    epochs = build_schedule(start_time, interval, end_time)

    errdir = 'error_' + str(uuid.uuid4())

    i = 0
    # set the output directory for the callback with a lambda
    with Acquisition(image_process_fn=lambda img, meta: img_process_fn(img, meta, outdir, errdir)) as acq:
        for t_target in epochs:
            # skip over times that have already passed when starting the program
            t_cur = time.time()
            t_target_str = datetime.fromtimestamp(t_target).isoformat()
            if t_cur > t_target:
                print('Skipping', t_target_str)
                continue

            # delay loop -- wait until each event and then take a picture
            print('Imaging at', t_target_str)
            t_cur = time.time()
            while t_target > t_cur:
                delay = t_target - t_cur
                print(f'Waiting {delay:8.2f} seconds', end='\r')
                if delay > 1:
                    delay = 1
                threading.Event().wait(delay)
                t_cur = time.time()

            # image is timestamped at acquisition to confirm it was taken at the expected time
            event = {
                'axes': {'idx': i, 'timestamp': time.time()}
            }
            if args.exposure:
                event['exposure'] = args.exposure
            acq.acquire(event)
            print('Image acquired!')
            i += 1
