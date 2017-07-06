#!/usr/bin/python3
# coding=utf-8

# This script replaces the original nocrash.sh functionality with a pure Python approach.

import platform
import os
import subprocess as sp
from time import sleep
import logging
import sys

# Set the Python Executable based on this being stored - we refer to this later on for subprocess calls.
PY_EXECUTABLE = sys.executable

# Log to errorlog.txt so that !!/errorlogs shows us restarts
logging.basicConfig(
    filename='nocrashlog.txt',
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(message)s')

count = 0
crashcount = 0
stoprunning = False
ecode = None  # Define this to prevent errors

# Make a clean copy of existing environment variables, to pass down to subprocess.
environ = os.environ.copy()

def log(message):
    logging.info('[NoCrash] {}'.format(message))
    print '[NoCrash] {}'.format(message)


def warn(message):
    logging.warn('[NoCrash] {}'.format(message))
    print '[NoCrash] {}'.format(message)


def error(message):
    logging.error('[NoCrash] {}'.format(message))
    print '[NoCrash] {}'.format(message)


while stoprunning is False:
    log('Starting')
    
    command = (PY_EXECUTABLE + ' bot.py').split()

    try:
        ecode = sp.call(command, env=environ)
    except KeyboardInterrupt:
        # print "[NoCrash] KeyBoard Interrupt received.."
        ecode = 6

    log('Exited with ecode {}'.format(ecode))

    if ecode == 6:
        log('Stopping')
        stoprunning = True
    else:
        error('Died for unknown reason -- check logs.  Sleeping before restart')
        sleep(5)