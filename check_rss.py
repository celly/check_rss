#!/usr/bin/env python3

'''
check_rss - A simple Nagios plugin to check an RSS feed.
Created to monitor status of cloud services.

Requires feedparser and argparse python libraries.

  python-feedparser python-argparse

on Debian or Redhat based systems

If you find it useful, feel free to leave me a comment/email
at  http://john.wesorick.com.


Copyright 2011 John Wesorick (john.wesorick.com)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

import feedparser
import argparse
import sys
import datetime
import math
import re

from io import StringIO
from html.parser import HTMLParser

'''
    Start: https://stackoverflow.com/questions/11061058/using-htmlparser-in-python-3-2
'''
class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.fed = []
    def handle_data(self, d):
        self.fed.append(d)
    def get_data(self):
        return ''.join(self.fed)

def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()

'''
    End: https://stackoverflow.com/questions/11061058/using-htmlparser-in-python-3-2
'''

''' 
    Start: https://stackoverflow.com/questions/4048651/python-function-to-convert-seconds-into-minutes-hours-and-days/4048773
''' 
def secondsToText(secs):
    days = secs//86400
    hours = (secs - days*86400)//3600
    minutes = (secs - days*86400 - hours*3600)//60
    seconds = secs - days*86400 - hours*3600 - minutes*60
    result = ("{0} day{1}, ".format(days, "s" if days!=1 else "") if days else "") + \
    ("{0} hour{1}, ".format(hours, "s" if hours!=1 else "") if hours else "") + \
    ("{0} minute{1}, ".format(minutes, "s" if minutes!=1 else "") if minutes else "") + \
    ("{0} second{1} ".format(seconds, "s" if seconds!=1 else "") if seconds else "")
    return result
'''
    End: https://stackoverflow.com/questions/4048651/python-function-to-convert-seconds-into-minutes-hours-and-days/4048773
'''

def fetch_feed_last_entry(feed_url):
    '''Fetch a feed from a given string'''

    try:
        myfeed = feedparser.parse(feed_url)
    except:
        exitcritical(("Could not parse feed: ", feed_url), '')

    if myfeed.bozo != 0:
        exitcritical(("Malformed feed: ", myfeed.bozo_exception), '')
    if (myfeed.status != 200):
        exitcritical(("Non 200 Status: ", myfeed.status), '')

    # feed with 0 entries are good too
    if (len(myfeed.entries) == 0):
        exitok('No news == good news', '')

    return myfeed.entries[0]


def main(argv=None):
    """Gather user input and start the check """
    description = "A simple Nagios plugin to check an RSS feed."
    epilog = """notes: If you do not specify any warning or
 critical conditions, it will always return OK.
 This will only check the newest feed entry.

 Copyright 2011 John Wesorick (http://john.wesorick.com)"""
    version = '0.3'

    # Set up our arguments
    parser = argparse.ArgumentParser(description=description,
                                  epilog=epilog)

    parser.add_argument('--version', action='version', version=version)

    parser.add_argument('-H', dest='rssfeed',
                         help='URL of RSS feed to monitor',
                         action='store',
                         required=True)

    parser.add_argument('-c', '--criticalif', dest='criticalif',
                         help='critical condition if PRESENT',
                         action='store')

    parser.add_argument('-C', '--criticalnot', dest='criticalnot',
                         help='critical condition if MISSING',
                         action='store')

    parser.add_argument('-w', '--warningif', dest='warningif',
                         help='warning condition if PRESENT',
                         action='store')

    parser.add_argument('-W', '--warningnot', dest='warningnot',
                         help='warning condition if MISSING',
                         action='store')

    parser.add_argument('-T', '--hours', dest='hours',
                         help='Hours since last post. '
                         'Will return critical if less than designated amount.',
                         action='store')

    parser.add_argument('-t', '--titleonly', dest='titleonly',
                         help='Search the titles only. The default is to search '
                         'for strings matching in either the title or description',
                         action='store_true',
                         default=False)

    parser.add_argument('-p', '--perfdata', dest='perfdata',
                         help='If used will keep very basic performance data '
                         '(0 if OK, 1 if WARNING, 2 if CRITICAL, 3 if UNKNOWN)',
                         action='store_true',
                         default=False)

    parser.add_argument('-v', '--verbosity', dest='verbosity',
                         help='Verbosity level. 0 = Only the title and time is returned. '
                         '1 = Title, time and link are returned. '
                         '2 = Title, time, link and description are returned (Default)',
                         action='store',
                         default='2')

    try:
        args = parser.parse_args()
    except:
        # Something didn't work. We will return an unknown.
        output = ': Invalid argument(s) {usage}'.format(usage=parser.format_usage())
        exitunknown(output)

    perfdata = args.perfdata

    # Parse our feed, getting title, description and link of newest entry.
    rssfeed = args.rssfeed
    if (rssfeed.find('http://') != 0 and rssfeed.find('https://') != 0):
        rssfeed = 'http://{rssfeed}'.format(rssfeed=rssfeed)

    # we have everything we need, let's start
    last_entry = fetch_feed_last_entry(rssfeed)
    feeddate = last_entry['updated_parsed']
    title = last_entry['title']
    description = last_entry['description']
    link = last_entry['link']


    # Get the difference in time from last post
    datetime_now = datetime.datetime.utcnow()
    datetime_feeddate = datetime.datetime(*feeddate[:6]) #http://stackoverflow.com/a/1697838/726716
    timediff = datetime_now - datetime_feeddate
    nice_time = secondsToText(math.floor(timediff.seconds))
    hourssinceposted = timediff.seconds/3600
    
    # We will form our response here based on the verbosity levels. This makes the logic below a lot easier.
    if (args.verbosity == '0'):
        output = 'Alert Age: %s \r\n%s' % (nice_time, title)
    elif (args.verbosity == '1'):
        output = 'Alert Age: %s \r\nTitle: %s \r\nLink: %s' % (nice_time, title, link)
    elif (args.verbosity == '2'):
        output = 'Alert Age: %s \r\nTitle: %s \r\nDescription: %s \r\nLink: %s' % (nice_time, title, description, link)

    # Remove Random HTML Tags
    output = strip_tags(output)
    output = re.sub(' +', ' ', output);

    # Check for strings that match, resulting in critical status
    if (args.criticalif):
        criticalif = args.criticalif.lower().split(',')
        for search in criticalif:
            if (args.titleonly):
                if (title.lower().find(search) >= 0):
                    exitcritical(output, perfdata)
            else:
                if (title.lower().find(search) >= 0 or description.lower().find(search) >= 0):
                    exitcritical(output, perfdata)

    # Check for strings that are missing, resulting in critical status
    if (args.criticalnot):
        criticalnot = args.criticalnot.lower().split(',')
        for search in criticalnot:
            if (args.titleonly):
                if (title.lower().find(search) == -1):
                    exitcritical(output, perfdata)
            else:
                if (title.lower().find(search) == -1 and description.lower().find(search) == -1):
                    exitcritical(output, perfdata)

    # Check for time difference (in hours), resulting in critical status
    if (args.hours):
        if (int(hourssinceposted) < int(args.hours)):
            exitcritical(output, perfdata)

    # Check for strings that match, resulting in warning status
    if (args.warningif):
        warningif = args.warningif.lower().split(',')
        for search in warningif:
            if (args.titleonly):
                if (title.lower().find(search) >= 0):
                    exitwarning(output, perfdata)
            else:
                if (title.lower().find(search) >= 0 or description.lower().find(search) >= 0):
                    exitwarning(output, perfdata)

    # Check for strings that are missing, resulting in warning status
    if (args.warningnot):
        warningnot = args.warningnot.lower().split(',')
        for search in warningnot:
            if (args.titleonly):
                if (title.lower().find(search) == -1):
                    exitwarning(output, perfdata)
            else:

                if (title.lower().find(search) == -1 and description.lower().find(search) == -1):
                    exitwarning(output, perfdata)

    # If we made it this far, we must be ok
    exitok(output, perfdata)


def exitok(output, perfdata):
    if (perfdata):
        print ("OK - ", output, "|'RSS'=0;1;2;0;2")
    else:
        print ("OK - ", output)
    sys.exit(0)


def exitwarning(output, perfdata):
    if (perfdata):
        print ("WARNING - ", output, "|'RSS'=1;1;2;0;2")
    else:
        print ("WARNING - ", output)
    sys.exit(1)


def exitcritical(output, perfdata):
    if (perfdata):
        print ("CRITICAL - ", output, "|'RSS'=2;1;2;0;2")
    else:
        print ("CRITICAL - ", output)
    sys.exit(2)


def exitunknown(output):
    sys.exit(3)

if __name__ == '__main__':
    result = main(sys.argv)
    sys.exit(result)
