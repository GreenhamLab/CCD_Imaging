#!/usr/bin/env python3

"""
---HELIOSCHEDULER (v1.0.0)---
Author/Maintainer: Stevan Zorich (zoric002@umn.edu)
PI: Katie Greenham (greenham@umn.edu)
Year: 2019

Generates schedule JSON configs for Heliospectra lights for use in luciferase-based CCD imaging.
Sets lights to turn off at a specified interval for a specified duration.

Requires Python 3.6 or greater to run.
"""

__author__ = "Stevan Zorich"
__copyright__ = "Copyright 2019, Greenham Lab"
__version__ = "2.0.0"


import json
import argparse as ap
from datetime import timedelta, datetime


# Exceptions for input time string processing. Times can either have an invalid format or invalid
# range.
class InvalidTimeFormatError(Exception):
    """exception for invalid time format in str_to_td"""
    pass


class InvalidTimeValueError(Exception):
    """exception for invalid time quantity (>24 hours or <0, or <=0 if selected)"""
    pass


# FUNCTION str_to_td(s, error_zero=True)
# Takes an input string to s and attempts to convert it to a Python timedelta object.
#
# Throws InvalidTimeFormatError if string is in an invalid format (valid formats are 24-hour
# HH:MM and HH:MM:SS). Throws InvalidTimeValueError if time is greater than 24 hours or less
# than 0. If error_zero is set to True (True by default) then InvalidTimeValueError will be thrown
# when time is equal to 0.
def str_to_td(s, error_zero=True):
    try:  # nested try to attempt both time formats before giving up
        t = datetime.strptime(s, "%H:%M:%S")
    except ValueError:
        try:
            t = datetime.strptime(s, "%H:%M")
        except ValueError:
            raise InvalidTimeFormatError

    t = timedelta(hours=t.hour, minutes=t.minute, seconds=t.second)
    if t > timedelta(days=1) or t < timedelta(0):  # bounds-check for input time
        raise InvalidTimeValueError
    if error_zero and t == timedelta(0):
        raise InvalidTimeValueError
    return t


# FUNCTION ev_str(td, i)
# Produces an event string (set intensity at specified time) represented as a Python dict.
# Takes a timedelta object and desired light intensity, respectively. Always sets white (5700 K)
# LEDs to off.
def ev_str(td, i):
    wavelengths = [380, 400, 420, 450, 530, 620, 660, 735, 5700]
    istr = []
    for wv in wavelengths:
        if wv == 5700:
            istr.append({"wl": wv, "i": 0})
        else:
            istr.append({"wl": wv, "i": i})
    # convert timedelta to HMS and make the event dict
    evstr = {"hour": td.seconds // 3600,
             "minute": td.seconds // 60 % 60,
             "second": td.seconds % 60,
             "intensities": istr}
    return evstr


# FUNCTION construct_schedule(name, start_td, int_td, dur_td, intensity)
# Constructs the entire nested-dict structure for a configuration file. Builds header, then
# constructs a schedule using the spcified start, interval, and duration times. The 'intensity'
# argument specifies the intensity of the lights when they are on. The 'name' arg is the name of
# the schedule in the config header.
def construct_schedule(name, start_td, int_td, dur_td, intensity):
    # note use of Python's // (integer divide): if the interval does not equally fit into 24 hours,
    # it will fill the schedule as far as it can, leaving an uneven gap after the last entry.
    num_intervals = timedelta(days=1) // int_td
    # list of events (as constructed in ev_str()) in dict structure
    event_list = []
    # generate two events at each interval: lights on, and then lights off after the duration
    for i in range(num_intervals):
        curr_td = start_td + int_td * i
        event_list.append(ev_str(curr_td, 0))
        event_list.append(ev_str(curr_td + dur_td, intensity))

    # header is populated with a weird 'wavelength' block that seems to exist for no reason
    default_wavelength_block = [{"wl": 380, "pwr": 280},
                                {"wl": 400, "pwr": 280},
                                {"wl": 420, "pwr": 280},
                                {"wl": 450, "pwr": 248},
                                {"wl": 530, "pwr": 744},
                                {"wl": 620, "pwr": 134},
                                {"wl": 660, "pwr": 268},
                                {"wl": 735, "pwr": 291},
                                {"wl": 5700, "pwr": 744}]
    schedule = {"text": name,
                "type": 0,
                "no_of_wave_lengths": 9,
                "no_of_events": num_intervals * 2,
                "wavelengths": default_wavelength_block,
                "events": event_list}
    return schedule


# MAIN SUBROUTINE
# Use Python's argparse to get arguments from the command line and generate a helpfile.
parser = ap.ArgumentParser(
    description="Generate Heliospectra light schedules that turn off at a certain interval, " +
    "for a certain duration. Times are input in 24-hour HH:MM or HH:MM:SS, " +
    "and must be no greater than 24 hours.")
parser.add_argument('start', metavar='start', type=str, nargs=1,
                    help='Start time.')
parser.add_argument('interval', metavar='interval', type=str, nargs=1,
                    help='Interval between captures (cannot be 00:00:00).')
parser.add_argument('duration', metavar='duration', type=str, nargs=1,
                    help='Duration of lights-off period (cannot be 00:00:00).')
parser.add_argument('intensity', metavar='intensity', type=int, nargs=1,
                    help='Intensity of lights when on (0 to 1000).')
parser.add_argument('-o', metavar='filename', type=str, nargs=1,
                    help='File to output (default schedule.txt).')
args = parser.parse_args()

# try/catch block for str_to_td functions
try:
    start = str_to_td(args.start[0], error_zero=False)
    interval = str_to_td(args.interval[0])
    duration = str_to_td(args.duration[0])

    # print warning if interval does not fit into 24 hours evenly
    if timedelta(days=1) % interval != timedelta(0):
        print(
            f"WARNING: Specified interval '{args.interval[0]}' does not evenly fit into 24 hours.")
        print(
            f"There will be an uneven gap in the schedule before {args.start[0]}. \n")

    if args.o is not None:
        fname = args.o[0]
    else:
        fname = "schedule.txt"

    sched_name = f"Generated by HelioScheduler on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    with open(fname, "w") as fp:
        json.dump(construct_schedule(sched_name, start,
                                     interval, duration, args.intensity[0]), fp, indent='\t')
    print("Configuration generated!\n")
except InvalidTimeFormatError:
    print("Invalid time format! Accepted formats are 24-hour HH:MM and HH:MM:SS")
except InvalidTimeValueError:
    print("Invalid time value! All times must be less than or equal to 24 hours.")
    print("Interval and duration cannot be 0.")
