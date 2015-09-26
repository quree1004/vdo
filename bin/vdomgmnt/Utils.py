"""
  Utils - miscellaneous utilities for the VDO manager

  Copyright (c) 2012-2013 Permabit Technology Corporation.
  @LICENSE@
  $Id: //eng/vdo-releases/nitrogen/src/c++/vdo/bin/vdomgmnt/Utils.py#1 $

"""
from . import Command, CommandError
import os
import time


class Utils(object):
  """Utils contains miscellaneous utilities."""

  def __init__(self):
    pass

  @staticmethod
  def maxNum(a, b):
    """Returns the maximum of two numbers."""
    if a > b:
      return a
    return b

  @classmethod
  def statusHelper(cls, commandList, tag):
    """Helper function for printing status summaries."""
    cmd = Command(commandList)
    s = cmd.runOutput()
    if s:
      print(tag + s.strip().translate(None, "\""))
    else:
      print(tag + _("not available"))

  @classmethod
  def killProcess(cls, pid, retries=20):
    """Kills a process, trying kill -9 as a last resort."""
    cmd = Command(['kill', str(pid)])
    try:
      cmd()
      if cmd.noRun:
        return
    except CommandError:
      return

    cmd = Command(['kill', '-0', str(pid)])
    for unused_count in range(retries):
      try:
        cmd()
        time.sleep(1)
      except CommandError:
        return

    cmd = Command(['kill', '-9', str(pid)])
    cmd.noThrowCall()

  @staticmethod
  def powerOfTwo(i):
    """Returns True iff its argument is a power of two."""
    return (i != 0) and ((i & (i - 1)) == 0)

  @staticmethod
  def appendToPath(path):
    """Appends a directory or directories to the current PATH.

    Arguments:
      path (str): A directory or colon-separated list of directories.
    """
    os.environ['PATH'] += os.pathsep + path

  @staticmethod
  def which(cmd):
    """Finds the full path to a command.

    Arguments:
      cmd (str): The command to search for.
    Returns:
      The full path as a string, or None if the command is not found.
    """
    for path in os.environ['PATH'].split(os.pathsep):
      testpath = os.path.join(path, cmd)
      if os.access(testpath, os.X_OK):
        return testpath
    return None

  @staticmethod
  def abspathPath(path):
    """Takes a path or a colon-separated list of paths and makes
    each one an absolute path. Paths that don't exist are left alone."""
    return os.pathsep.join([os.path.abspath(p) for p in path.split(os.pathsep)])
