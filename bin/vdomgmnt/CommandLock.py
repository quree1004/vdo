"""
  CommandLock - simple process locking

  Copyright (c) 2012-2013 Permabit Technology Corporation.
  @LICENSE@
  $Id: //eng/vdo-releases/nitrogen/src/c++/vdo/bin/vdomgmnt/CommandLock.py#1 $

"""
from . import CommandError, Logger
import errno
import fcntl
import os
import time

class CommandLockTimeout(Exception):
  """Exception raised to indicate a timeout acquiring a CommandLock."""
  def __init__(self, msg):
    super(CommandLockTimeout, self).__init__()
    self._msg = msg
  def __str__(self):
    return self._msg


class CommandLock(object):
  """Simple process locking.

  Attributes:
    _fd (int): file descriptor if the lock file is open
    _filename (string): path to the lock file
    _locked (bool): True iff we hold the lock
    _lockRetries (int): number of retries to attempt at 1 second
                        intervals before failing
    _readonly (bool): True iff this is a shared (read) lock
  """
  log = Logger.getLogger(Logger.myname + '.CommandLock')

  def __init__(self, filename, readonly=True):
    self._fd = -1
    self._filename = filename
    self._locked = False
    self._lockRetries = 20
    self._readonly = readonly

  def __str__(self):
    return "CommandLock(\"{0}\")".format(self._filename)

  def __repr__(self):
    lst = [self.__str__(), "["]
    lst.append(','.join('='.join([key, str(getattr(self, key))])
                        for key in self.__dict__))
    lst.append("]")
    return "".join(lst)

  def lock(self):
    """Lock this command by taking a record lock on a lockfile.
    Raises CommandException in case of an error or timeout.
    """
    self._openLockFile()

    for unused_count in range(self._lockRetries):
      try:
        if self._readonly:
          fcntl.flock(self._fd, fcntl.LOCK_SH|fcntl.LOCK_NB)
        else:
          fcntl.flock(self._fd, fcntl.LOCK_EX|fcntl.LOCK_NB)
        self._locked = True
        return
      except IOError as e:
        if e.errno != errno.EACCES and e.errno != errno.EAGAIN:
          raise CommandError(_("Could not lock file {0}: {1}").format(
              self._filename, e.strerror))
        else:
          time.sleep(1)
    raise CommandLockTimeout(_("Could not lock {0}: timed out").format(
        self._filename))

  def unlock(self):
    """Unlock this object."""
    if self._locked:
      fcntl.flock(self._fd, fcntl.LOCK_UN)
      os.close(self._fd)
      self._fd = -1
      self._locked = False
      self.log.debug("Unlocked {0}".format(self._filename))

  def _openLockFile(self):
    """Open the lock file for this object, creating it if necessary.

    Note: for the time being, the lockfile is created with mode
    666. This is necessary because we're still putting an exclusive
    lock around every command and we still support non-root use of
    some vdo commands.
    """
    oldmask = os.umask(000)
    try:
      if self._readonly:
        self.log.debug("Locking {0} for read".format(self._filename))
        self._fd = os.open(self._filename, os.O_CREAT|os.O_RDONLY, 0666)
      else:
        self.log.debug("Locking {0} for write".format(self._filename))
        self._fd = os.open(self._filename, os.O_CREAT|os.O_RDWR, 0666)
    except OSError as e:
      raise CommandError(_("Could not open lock file {0}: {1}").format(
          self._filename, e.strerror))
    finally:
      os.umask(oldmask)

  def __enter__(self):
    if not self._locked:
      self.lock()
    return self

  def __exit__(self, unused_type, unused_value, unused_traceback):
    self.unlock()

  def __del__(self):
    self.unlock()
