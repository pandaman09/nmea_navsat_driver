# Software License Agreement (BSD License)
#
# Copyright (c) 2013, Eric Perko
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#  * Neither the names of the authors nor the names of their
#    affiliated organizations may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import re
import time
import calendar
import math
import logging
logger = logging.getLogger('rosout')


def safe_float(field):
    try:
        return float(field)
    except ValueError:
        return float('NaN')


def safe_int(field):
    try:
        return int(field)
    except ValueError:
        return 0


def convert_latitude(field):
    return safe_float(field[0:2]) + safe_float(field[2:]) / 60.0


def convert_longitude(field):
    return safe_float(field[0:3]) + safe_float(field[3:]) / 60.0


def convert_time(nmea_utc):
    # Get current time in UTC for date information
    utc_struct = time.gmtime()  # immutable, so cannot modify this one
    utc_list = list(utc_struct)
    # If one of the time fields is empty, return NaN seconds
    if not nmea_utc[0:2] or not nmea_utc[2:4] or not nmea_utc[4:6]:
        return float('NaN')
    else:
        hours = int(nmea_utc[0:2])
        minutes = int(nmea_utc[2:4])
        seconds = int(nmea_utc[4:6])
        utc_list[3] = hours
        utc_list[4] = minutes
        utc_list[5] = seconds
        unix_time = calendar.timegm(tuple(utc_list))
        return unix_time


def convert_status_flag(status_flag):
    if status_flag == "A":
        return True
    elif status_flag == "V":
        return False
    else:
        return False


def convert_knots_to_mps(knots):
    return safe_float(knots) * 0.514444444444


# Need this wrapper because math.radians doesn't auto convert inputs
def convert_deg_to_rads(degs):
    return math.radians(safe_float(degs))

"""Format for this is a sentence identifier (e.g. "GGA") as the key, with a
tuple of tuples where each tuple is a field name, conversion function and index
into the split sentence"""
parse_maps = {
    "GGA": [
        ("fix_type", safe_int, 6),
        ("latitude", convert_latitude, 2),
        ("latitude_direction", str, 3),
        ("longitude", convert_longitude, 4),
        ("longitude_direction", str, 5),
        ("altitude", safe_float, 9),
        ("mean_sea_level", safe_float, 11),
        ("hdop", safe_float, 8),
        ("num_satellites", safe_int, 7),
        ("utc_time", convert_time, 1),
        ],
    "VTG": [
        ("speed_knots", safe_float, 5),
        ("speed_kph", safe_float, 7),
        ("mode", str, 9),
        ],
#    "GST": [
# GST data contains error information
#    ],
    "PJT": [
        #Trimble proprietary
        ("coordinate_system", str, 1),
        ("project_name", str, 2)
        ],
    "AVR": [
        ("yaw", safe_float, 2),
        ("pitch", safe_float, 4),
        ("roll", safe_float, 6),
        ("fix_type", safe_int, 9),
        ("PDOP", safe_int, 20),
        ("num_satellites", safe_int, 11),
        ],
    "HDT": [
        ("heading_north", safe_float, 1)
        ],
    "ROT": [
        ("rate",safe_int, 1),
        ("validity", str, 2),
        ],
    "RMC": [
        ("utc_time", convert_time, 1),
        ("fix_valid", convert_status_flag, 2),
        ("latitude", convert_latitude, 3),
        ("latitude_direction", str, 4),
        ("longitude", convert_longitude, 5),
        ("longitude_direction", str, 6),
        ("speed", convert_knots_to_mps, 7),
        ("true_course", convert_deg_to_rads, 8),
        ],
#    "DG": [
# DG contains L-Band corrections and beacon signal strength
#        ],
#    "GBS": [
# GBS data contains expected error in various data
#        ],
#    "GNS": [
# GNS data contains less accurate long,lat, mode indicator, HDOP, MSL, geoidal separation, age of data
#        ],
    "LLQ": [
        ("easting", safe_float, 3),
        ("northing", safe_float, 5),
        ("fix_type", safe_int, 7),
        ("position_quality", safe_float, 9),
        ("height", safe_float, 10),
        ("utc_time", convert_time, 1),
        ]
    }


def parse_nmea_sentence(nmea_sentence):
    # Check for a valid nmea sentence
    # Added PTNL for trimble proprietary messages
    if not re.match('^\$(GP|GN|PTNL).*\*[0-9A-Fa-f]{2}$', nmea_sentence):
        logger.debug("Regex didn't match, sentence not valid NMEA? Sentence was: %s"
                     % repr(nmea_sentence))
        return False
    fields = [field.strip(',') for field in nmea_sentence.split(',')]
    #Check if nmea sentence contains trimble proprietary message
    sentence_type = ""
#   trimble_msg = False
    if re.match('^\$(PTNL).*\*[0-9A-Fa-f]{2}$', nmea_sentence):
#       trimble_msg = True
        if fields[0].find("PTNLDG") :
            #DG message type isn't comma seperated on trimble BD9xx reciever
            sentence_type = "DG"
        else:
            #Ignore the $ and talker ID portion "PTNL"
            sentence_type = fields[0][5:]
    else:
      # Ignore the $ and talker ID portions (e.g. GP)
      sentence_type = fields[0][3:]

    if not sentence_type in parse_maps:
        logger.debug("Sentence type %s not in parse map, ignoring."
                     % repr(sentence_type))
        return False

    parse_map = parse_maps[sentence_type]

    parsed_sentence = {}
    for entry in parse_map:
        parsed_sentence[entry[0]] = entry[1](fields[entry[2]])
    return {sentence_type: parsed_sentence}
