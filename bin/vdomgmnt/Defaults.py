"""
  Defaults - manage Albireo/VDO defaults

  Copyright (c) 2012-2013 Permabit Technology Corporation.
  @LICENSE@
  $Id: //eng/vdo-releases/nitrogen/src/c++/vdo/bin/vdomgmnt/Defaults.py#7 $

"""
from . import Logger, SizeString, Utils
import optparse
import os
import re


class ArgumentError(Exception):
  """Exception raised to indicate an error with an argument."""
  def __init__(self, msg):
    super(ArgumentError, self).__init__()
    self._msg = msg
  def __str__(self):
    return self._msg


class Defaults(object):
  """Defaults manages default values for arguments."""

  NOTSET = -1
  address = 'localhost'
  albireoIndexDir = '/mnt/dedupe-index'
  albireoMem = 0
  albireoSparse = False
  blockMapCacheSize = SizeString("128M")
  blockMapPageSize = 32768
  cfreq = 0
  confFile = os.getenv('VDO_CONF_DIR', '/etc') + '/vdoconf.xml'
  customFile = os.getenv('VDO_CONF_DIR', '/etc') + '/vdocustom.xml'
  enable512e = False
  enabled = True
  enableCompression = False
  enableDeduplication = True
  log = Logger.getLogger(Logger.myname + '.Defaults')
  mdRaid5Mode = 'on'
  port = 8000
  readCacheSize = SizeString("0")
  recoveryScanRate = 640
  recoverySweepRate = 40
  reserveSize = SizeString("0")
  udsParallelFactor = 0
  vdoPhysicalBlockSize = 4096
  vdoLogLevel = 'info'
  volumeGroup = 'dedupevg'
  # Default write policy for configuration; handles missing external
  # configuration scenarios.
  configuredWritePolicy = 'read_from_superblock'
  # Default write policy for command-line arguments; corresponds to default
  # value used within base code at initialization if no external configuration
  # information is available.
  externalWritePolicy = 'sync'

  def __init__(self):
    pass

  @classmethod
  def getAlbireoIndexDir(cls, args):
    """Returns the albireoIndexDir from an OptionParser options object
    or a default constructed from the VDO name.

    Arguments:
      args: The OptionParser argument object.
    Raises:
      ArgumentError
    """
    if args.albireoIndexDir:
      return args.albireoIndexDir
    if not args.name:
      raise ArgumentError(_("Missing required argument '--name'"))
    return cls.albireoIndexDir + "-" + args.name

  @classmethod
  def _getAlbireoSizeG(cls, args):
    """Calculates default size for an Albireo index in gigabytes.

    Arguments:
      args: The OptionParser argument object.
    Returns:
      A float giving the default size in gigabytes.
    """
    albNeedGB = 20.00
    albireoMem = float(args.albireoMem)
    if albireoMem == 0.0:
      albireoMem = 1.0
    albNeedGB = 20.00 * albireoMem
    if args.albireoSparse:
      albNeedGB *= 10.0
    return albNeedGB

  @classmethod
  def getLvNames(cls, args):
    """Return a tuple (lvIndex, lvVdo) of logical volume names, either
    the ones specified by the user or defaults constructed from the
    VDO volume name as appropriate.

    Arguments:
      args: the OptionParser options object
    Raises:
      ArgumentError
    """
    lvIndex = args.name + "-index"
    lvVdo = args.name + "-backing"
    if args.lvIndex:
      lvIndex = args.lvIndex
    if args.lvVdo:
      lvVdo = args.lvVdo
    return lvIndex, lvVdo

  @classmethod
  def getAlbireoSize(cls, args):
    """Returns the default size for an Albireo index.

    Arguments:
      args: The OptionParser argument object.
    Returns:
      The default size, as a SizeString.
    """
    if args.albireoSize:
      return args.albireoSize
    retval = SizeString(str(cls._getAlbireoSizeG(args)) + 'G')
    cls.log.debug("Calculated index size: {0!s}".format(retval))
    return retval

  @staticmethod
  def checkAbspath(unused_option, opt, value):
    """Checks that an option is an absolute pathname.

    Arguments:
      opt (str): Name of the option being checked.
      value (str): Value provided as an argument to the option.
    Returns:
      The pathname as a string.
    Raises:
      OptionValueError
    """
    if os.path.isabs(value):
      return value
    raise optparse.OptionValueError(
      _("option %s: must be an absolute pathname") % (opt))

  @staticmethod
  def checkAlbmem(unused_option, opt, value):
    """Checks that an option is a legitimate Albireo memory setting.

    Arguments:
      opt (str): Name of the option being checked.
      value (str): Value provided as an argument to the option.
    Returns:
      The memory setting as a string.
    Raises:
      OptionValueError
    """
    try:
      if value == '0.25' or value == '0.5' or value == '0.75':
        return value
      int(value)
      return value
    except ValueError:
      pass
    raise optparse.OptionValueError(
      _("option %s: must be an Albireo memory value") % (opt))

  @staticmethod
  def checkLv(unused_option, opt, value):
    """Checks that an option is a valid name for a logical volume.

    Note: the LVM documentation does not state what constitutes a
    valid logical volume name. For now, we just check for slashes.

    Arguments:
      opt (str): Name of the option being checked.
      value (str): Value provided as an argument to the option.
    Returns:
      The logical volume name as a string.
    Raises:
      OptionValueError
    """
    if value.find("/") < 0:
      return value
    raise optparse.OptionValueError(
      _("option %s: logical volume names cannot contain slashes") % (opt))

  @staticmethod
  def checkPagesz(unused_option, opt, value):
    """Checks that an option is an acceptable value for a page size.
    Page sizes must be a power of 2, and are normally interpreted as a
    byte count. The suffixes 'K' and 'M' may be used to specify
    kilobytes or megabytes, respectively.

    Arguments:
      opt (str): Name of the option being checked.
      value (str): Value provided as an argument to the option.
    Returns:
      The value converted to an integer byte count.
    Raises:
      OptionValueError
    """
    try:
      multipliers = {'k': 1024, 'm': 1048576}
      m = re.match(r"^(\d+)([kKmM])?$", value)
      if (m):
        nbytes = int(m.group(1))
        if m.group(2):
          nbytes *= multipliers[m.group(2).lower()]
        if Utils.powerOfTwo(nbytes):
          return nbytes
    except ValueError:
      pass
    raise optparse.OptionValueError(
      _("option %s: must be a power of 2, K/M suffix optional") % (opt))

  @staticmethod
  def checkPow2(unused_option, opt, value):
    """Checks that an option is an integer power of two.

    Arguments:
      opt (str): Name of the option being checked.
      value (str): Value provided as an argument to the option.
    Returns:
      The value converted to an integer.
    Raises:
      OptionValueError
    """
    try:
      n = int(value)
      if Utils.powerOfTwo(n):
        return n
    except ValueError:
      pass
    raise optparse.OptionValueError(
      _("option %s: must be an integer power of 2") % (opt))

  @staticmethod
  def checkSize(unused_option, opt, value):
    """Checks that an option is an LVM-style size string.

    Arguments:
      opt (str): Name of the option being checked.
      value (str): Value provided as an argument to the option.
    Returns:
      The value converted to a SizeString.
    Raises:
      OptionValueError
    """
    try:
      ss = SizeString(value)
      return ss
    except ValueError:
      pass
    raise optparse.OptionValueError(
      _("option %s: must be an LVM-style size string") % (opt))

  @staticmethod
  def checkVg(unused_option, opt, value):
    """Checks that an option is a valid name for a volume group.

    Note: the LVM documentation does not state what constitutes a
    valid volume group name. For now, we just check for slashes.

    Arguments:
      opt (str): Name of the option being checked.
      value (str): Value provided as an argument to the option.
    Returns:
      The logical volume name as a string.
    Raises:
      OptionValueError
    """
    if value.find("/") < 0:
      return value
    raise optparse.OptionValueError(
      _("option %s: volume group names cannot contain slashes") % (opt))
