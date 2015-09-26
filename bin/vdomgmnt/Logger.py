"""
  Logger - VDO manager logging

  Copyright (c) 2013 Permabit Technology Corporation.
  @LICENSE@
  $Id: //eng/vdo-releases/nitrogen/src/c++/vdo/bin/vdomgmnt/Logger.py#1 $

"""
import logging
import logging.handlers
import os
import sys


class Logger(object):
  """Wrappers and configuration methods for the Python logger.

  Attributes:
    myname (string): name of the command being run.
    quiet (bool): if True, don't print to stdout.
  """
  myname = os.path.basename(sys.argv[0])
  mypath = os.path.abspath(__file__)
  quiet = False

  def __init__(self):
    pass

  @classmethod
  def getLogger(cls, name):
    """Returns a Python logger decorated with the announce method."""
    from types import MethodType
    logger = logging.getLogger(name)
    logger.announce = MethodType(cls.announce, logger, logging.Logger)
    return logger

  @classmethod
  def announce(cls, logger, msg):
    """Print a status message to stdout and log it as well."""
    if not cls.quiet:
      print(msg)
    logger.info(msg)

  @classmethod
  def configure(cls, name, path, options):
    """Configure the logging system according to command line options."""
    cls.myname = name
    cls.mypath = path
    if 'VDO_DEBUG' in os.environ:
      debugenv = int(os.environ['VDO_DEBUG']) != 0
    else:
      debugenv = False
    if options.debug or debugenv:
      logging.basicConfig(format='%(name)s: %(levelname)s: %(message)s',
                          level=logging.DEBUG)
    else:
      logging.basicConfig(format= cls.myname + ': %(levelname)s: %(message)s',
                          level=logging.WARN)
    if options.syslog:
      handler = logging.handlers.SysLogHandler(address = '/dev/log')
      formatter = logging.Formatter(cls.myname
                                    + ': %(levelname)s: %(message)s')
      handler.setFormatter(formatter)
      logging.getLogger().addHandler(handler)

