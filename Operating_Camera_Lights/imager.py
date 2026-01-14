#!/usr/bin/env python3

"""
---IMAGER (v2.1.0)---
Author: Stevan Zorich (zoric002@umn.edu)
Maintainer: William Gustafson (gust1020@umn.edu/williamlgustafson@gmail.com)
PI: Katie Greenham (greenham@umn.edu)
Changelog:
	2021 - Original version by Stevan
	2026-01-05 - Edits by William
		Switched to use MMCore api because old version stopped working because ???
	2026-01-09 - Added info messages for when input times are incorrect

Integrates with micro-manager using the pycromanager library to take time-series images at
constant intervals starting and ending at a scheduled date/time.

Requires Python 3.6 or greater to run.

Tested on Python 3.13
"""

__author__ = "Stevan Zorich"
__copyright__ = "Copyright 2021, Greenham Lab"
__version__ = "2.1.0"


import argparse
import time
import threading
import sys
import os
import uuid
import numpy as np
from datetime import datetime
from pathlib import Path
from PIL import Image
from pycromanager import Core


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
	parser = argparse.ArgumentParser(epilog='Version '+__version__)
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
def img_process_fn(image, timestamp, export_path, err_path):
	img = Image.fromarray(image)
	dt = datetime.fromtimestamp(timestamp)
	timestr = dt.strftime(FILE_FMT)
	imname = f'{timestr}_img.tif'
	filepath = os.path.join(export_path, imname)
	try:
		print('Saving image to:',filepath)
		img.save(filepath)
	except FileNotFoundError:
		print('Error: Could not write to directory',export_path)
		if not os.path.exists(err_path):
			os.mkdir(err_path)
		img.save(os.path.join(err_path,imname))
		print('Saved backup to',os.path.join(err_path,imname))

# MAIN SUBROUTINE
if __name__ == "__main__":
	parser = build_parser()
	args = parser.parse_args()
	outdir = args.out


	core = Core()
	core.set_exposure(args.exposure)
   
	start_time = dtstr_to_epoch(args.start, DT_FMT)
	interval = tstr_to_interval(args.interval, INTERVAL_FMT)
	end_time = dtstr_to_epoch(args.end, DT_FMT)
	epochs = build_schedule(start_time, interval, end_time)

	errdir = 'error_' + str(uuid.uuid4())

	i = 0

	t_cur = time.time()
	if sum(e>t_cur for e in epochs)==0:
		if end_time < time.time():
			print("End time is in the past, not taking any images.")
		if start_time > end_time:
			print("Start time is after end time, not taking any images.")
		else:
			print("No sample times in range (this may be a bug), not taking any images.")
	print(f"Skipping {sum(t_cur>e for e in epochs)} time points")
	epochs = [e for e in epochs if t_cur<e]
	for t_target in epochs:
		
		
		t_target_str = datetime.fromtimestamp(t_target).isoformat()

		if t_cur > t_target:
			print('Warning skipping', t_target_str, 'exposure may have run in to next time point.')
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
		timestamp = time.time()
		core.snap_image()
		# "If using micro-manager multi-camera adapter, use core.getTaggedImage(i), where i is
		# the camera index"
		# I don't know what that means
		tagged_image = core.get_tagged_image()
		print('Image taken')
		pixels = np.reshape(tagged_image.pix, [tagged_image.tags["Height"], tagged_image.tags["Width"]])
		print(pixels)
		img_process_fn(pixels, timestamp, outdir, errdir)
		print('Image saved')
		i += 1
