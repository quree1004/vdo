"""
  SizeString - LVM-style size strings

  Copyright (c) 2012-2013 Permabit Technology Corporation.
  @LICENSE@
  $Id: //eng/vdo-releases/nitrogen/src/c++/vdo/bin/vdomgmnt/SizeString.py#1 $

"""
import locale


class SizeString(object):
  """Represents the size of an object such as a disk partition.

  Conversions are provided to and from suffixed size strings as used
  by LVM commands like lvcreate(8). These strings consist of a
  (possibly floating-point) number followed by an optional unit
  suffix: B (bytes), S (512-byte sectors), and KMGPE for kilobytes
  through exabytes, respectively. Suffixes are not case-sensitive; the
  default unit is Megabytes. Currently, we reject negative sizes.

  The B and S suffixes are not documented but do appear to be used in
  some or all LVM commands. Unlike some (but not all) LVM commands we
  do not interpret the upper-case version of a suffix as a power of
  ten.

  Attributes:
    _originalString (str): the original string we were constructed
      with, mainly used for debugging
    _bytes (int): the value of this object in bytes

  """
  _defaultSuffix = 'm'
  _multipliers = {'b': 1, 's': 512, 'k': 1024, 'm': 1048576,
                  'g': 1073741824, 't': 1099511627776,
                  'p': 1125899906842624, 'e': 1152921504606846976}

  def __init__(self, sz):
    self._originalString = sz
    if sz:
      try:
        suffix = sz[-1:].lower()
        if suffix in self._multipliers:
          nbytes = self._atof(sz[:-1])
        else:
          nbytes = self._atof(sz)
          suffix = self._defaultSuffix
      except ValueError:
        raise ValueError(_("invalid size string \"{size}\"").format(size=sz))
      nbytes *= float(self._multipliers[suffix])
      self._bytes = int(nbytes)
      if self._bytes < 0:
        raise ValueError(_("invalid size string \"{size}\"").format(size=sz))
    else:
      self._bytes = 0

  def __nonzero__(self):
    return self._bytes != 0

  def __long__(self):
    return self._bytes

  def __add__(self, rhs):
    retval = SizeString("")
    retval._bytes = self._bytes + long(rhs)
    return retval

  def __iadd__(self, rhs):
    self._bytes += long(rhs)
    return self

  def __cmp__(self, rhs):
    return cmp(self._bytes, rhs.toBytes())

  def __str__(self):
    return self.asInteger()

  def __repr__(self):
    return self._originalString + " (" + str(self._bytes) + "B)"

  @staticmethod
  def _atof(s):
    """Tries to convert a float using the current LC_NUMERIC settings.
    If something goes wrong, tries float().
    """
    try:
      return locale.atof(s)
    except:
      return float(s)

  def asDisplay(self):
    """Returns a displayable representation of this object as a string.

    This follows the LVM convention of displaying friendly output
    rather than being completely accurate, due to rounding; do not use
    this method for computation or input to another program.
    """
    if self._bytes == 0:
      return "0"
    for click in ['e', 'p', 't', 'g', 'm', 'k']:
      divisor = self._multipliers[click]
      if self._bytes >= divisor:
        return '%2.2f%c' % (float(self._bytes) / divisor, click.upper())
    return str(self._bytes) + "B"

  def toSectors(self):
    """Returns this object as a count of 512-byte sectors, rounding up."""
    bytesPerSector = self._multipliers['s']
    return (self._bytes + (bytesPerSector - 1)) / bytesPerSector

  def round(self, blockSize):
    """Rounds this object down to a multiple of a given block size."""
    self._bytes = (self._bytes // blockSize) * blockSize

  def asInteger(self):
    """Returns this object as a size string without a decimal point."""
    if self._bytes == 0:
      return "0"
    for click in ['e', 'p', 't', 'g', 'm', 'k']:
      divisor = self._multipliers[click]
      if self._bytes % divisor == 0:
        return str(self._bytes // divisor) + click.upper()
    return str(self._bytes) + "B"

  def toBytes(self):
    """Returns the count of bytes represented by this object."""
    return self._bytes
