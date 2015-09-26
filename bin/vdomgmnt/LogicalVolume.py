"""
  LogicalVolume - manage index and backing storage

  Copyright (c) 2013 Permabit Technology Corporation.
  @LICENSE@
  $Id: //eng/vdo-releases/nitrogen/src/c++/vdo/bin/vdomgmnt/LogicalVolume.py#2 $

"""
from . import Command, CommandError, ArgumentError, Logger, SizeString
import os


class LogicalVolume(object):
  """LogicalVolume manages the storage used for the Albireo index and
  for backing the VDO device. Note that LogicalVolumes may or may not
  correspond to an actual logical volume on the local system; the
  constructor only checks syntax. The attributes _lvpath, _name, and
  _volumeGroup are simply for convenience and are set from the
  fullpath constructor argument.

  Attributes:
    _fullpath (str): the full pathname for the logical volume
      (e.g., /dev/vgname/lvname)
    _lvpath (str): the LVM path for the logical volume (vgname/lvname)
    _name (str): the name of the logical volume (lvname)
    _physicalSize (SizeString): the size set in create or growPhysical;
      only used to support fake returns in noRun
    _volumeGroup (str): the name of the volume group (vgname)
    maximumSize (SizeString): if set, attempts to create or extend
      this volume's physical size past maximumSize will raise an
      ArgumentError
  """
  log = Logger.getLogger(Logger.myname + '.LogicalVolume')
  lvmFlavor = 'LVM'

  def __init__(self, fullpath):
    """Constructs a logical volume.

    Note: the LVM documentation does not state what constitutes a
    valid logical volume name. For now, we just check for slashes.

    Arguments:
      fullpath (str): the full path to the device
    Exceptions:
      ArgumentError: invalid fullpath
    """
    if fullpath.count(os.sep) != 3 or fullpath[:5] != '/dev/':
      raise ArgumentError(_("Invalid logical volume path {path}").format(
          path=fullpath))
    self._fullpath = fullpath
    self._volumeGroup, self._name = os.path.split(fullpath)
    self._volumeGroup = os.path.basename(self._volumeGroup)
    self._lvpath = os.sep.join([self._volumeGroup, self._name])
    self._physicalSize = SizeString('')
    self.maximumSize = None

  def __str__(self):
    """Returns a string representation of this logical volume. This is
    also used to persist LogicalVolumes in the configuration file and
    must produce a string that can be passed to the constructor to
    recreate this object."""
    return self._fullpath

  def __repr__(self):
    lst = ["LogicalVolume", "["]
    lst.append(','.join('='.join([key, str(getattr(self, key))])
                        for key in self.__dict__))
    lst.append("]")
    return "".join(lst)

  def __cmp__(self, rhs):
    return cmp(self._fullpath(), rhs.fullpath())

  def canCreate(self):
    """Tests whether this LogicalVolume can be created. The volume
    group must exist and the logical volume must not exist.

    Exceptions:
      ArgumentError: this LogicalVolume cannot be created
    """
    vgsCmd = Command(['vgs', self._volumeGroup])
    try:
      vgsCmd()
    except CommandError:
      raise ArgumentError(_("Volume group {vg} does not exist").format(
          vg=self._volumeGroup))
    if self.exists():
      raise ArgumentError(_("Logical volume {lv!s} already exists").format(
          lv=self))

  def create(self, blockSize, physicalSize=None):
    """Creates this logical volume.

    Arguments:
      blockSize (int): the block size in bytes
      physicalSize (SizeString): the desired size of the volume;
        if None, allocate the remaining space in the volume group
    Returns:
      The physical size of the created volume as a SizeString.
    Exceptions:
      CommandError: a logical volume command failed
    """
    self._physicalSizeCheck(physicalSize, False)
    cmdList = ["lvcreate", "--name", self._lvpath]
    if physicalSize:
      self._physicalSize = physicalSize
      cmdList.extend(["--size", str(physicalSize)])
    else:
      cmdList.extend(["--extents", "100%FREE"])
    cmdList.append(self._volumeGroup)
    lvcreateCmd = Command(cmdList)
    lvcreateCmd()
    return self._roundSize(blockSize, physicalSize)

  def remove(self, noThrow=False):
    """Removes this logical volume.

    Arguments:
      noThrow (bool): if True, swallow exceptions
    Exceptions:
      CommandError: a logical volume command failed
    """
    lvchangeCmd = Command(['lvchange', '-an', self._lvpath])
    lvremoveCmd = Command(['lvremove', '-f', self._lvpath])
    try:
      lvchangeCmd.waitFor(10)
      lvremoveCmd.waitFor(10)
      self._physicalSize = SizeString('')
    except CommandError as ex:
      if noThrow:
        self.log.warn(_("Could not remove {lv}: {ex}").format(lv=self._lvpath,
                                                              ex=ex))
      else:
        raise

  def exists(self):
    """Tests whether this logical volume exists."""
    if not os.path.exists(self._lvpath):
      return False
    lvsCmd = Command(['lvs', self._lvpath])
    try:
      lvsCmd()
      return True
    except CommandError:
      return False

  def extend(self, blockSize, physicalSize=None):
    """Extends this logical volume.

    Arguments:
      blockSize (int): the block size in bytes
      physicalSize (SizeString): the desired size of the volume;
        if None, allocate the remaining space in the volume group
    Returns:
      The physical size of the extended volume as a SizeString.
    Exceptions:
      CommandError: a logical volume command failed
    """
    self._physicalSizeCheck(physicalSize, True)
    cmdList = ['lvextend']
    if physicalSize:
      self._physicalSize = physicalSize
      cmdList.extend(['--size', str(physicalSize)])
    else:
      cmdList.extend(['--extents', '+100%FREE'])
    cmdList.append(self._lvpath)
    lvextendCmd = Command(cmdList)
    lvextendCmd()
    return self._roundSize(blockSize, physicalSize)

  def reduce(self, physicalSize):
    """Reduces the size of this logical volume. Swallows exceptions.

    Arguments:
      physicalSize (SizeString): the desired physical size
    """
    lvchangenCmd = Command(['lvchange', '-an', self._lvpath])
    lvreduceCmd = Command(['lvreduce', '--size', str(physicalSize),
                           '--force', self._lvpath])
    lvchangeyCmd = Command(['lvchange', '-ay', self._lvpath])
    lvchangenCmd.noThrowCall()
    lvreduceCmd.noThrowCall()
    lvchangeyCmd.noThrowCall()
    self._physicalSize = physicalSize

  def getSize(self):
    """Returns the size of this logical volume as a SizeString. If
    noRun is set, returns the value we saved at create/growPhysical.
    Note that this may be zero bytes if the default (remaining free
    space) was requested.

    Returns:
      The size as a SizeString, zero-byte if an error occurred.
    """
    lvsCmd = Command(['lvs', '--units', 'k', '--noheadings',
                      '--nosuffix', '-o', 'lv_size', self._lvpath])
    if lvsCmd.noRun:
      return self._physicalSize
    kbytes = lvsCmd.runOutput().strip()
    if not kbytes:
      return SizeString('')
    return SizeString(kbytes + 'K')

  def fullpath(self):
    """Returns the full pathname of this logical volume. This method
    is used to persist LogicalVolumes and must produce a string that
    can be passed to the constructor to recreate this object."""
    return self._fullpath

  def status(self):
    """Returns the status of this logical volume. This is simply the
    raw information from the lvs command. Returns "(not available)"
    if the information is not available."""
    lvsCmd = Command(['lvs', '--noheadings', self._lvpath])
    lvsResult = lvsCmd.runOutput().strip()
    if lvsResult:
      return lvsResult
    else:
      return _("(not available)")

  def vgStatus(self):
    """Returns the status of the volume group associated with this
    logical volume. This is simply the raw information from the vgs
    command. Returns "(not available)" if the information is not
    available."""
    vgsCmd = Command(['vgs', '--noheadings', self._volumeGroup])
    vgsResult = vgsCmd.runOutput().strip()
    if vgsResult:
      return vgsResult
    else:
      return _("(not available)")


  def setAvailable(self, yorn):
    """Makes the logical volume available or unavailable

    Arguments:
      yorn (Boolean)  if True, set the volume available,
                      if False, set the volume unavailable
    """
    arg = '-ay' if yorn else '-an'
    lvchangeCmd = Command(['lvchange', arg, self._lvpath])
    try:
      lvchangeCmd()
    except CommandError as ex:
      self.log.error(_("Could not activate {0}: {1!s}").format(str(self), ex))
    return

  def _roundSize(self, blockSize, expected=None):
    """Finishes a create or extend operation by rounding the size of
    the volume down to a multiple of a given block size if necessary.
    Also reports any fiddling the LVM may have done with a requested
    size.

    Arguments:
      blockSize (int): the block size in bytes
      expected (SizeString): if provided, check the size of the
        volume before doing anything, and if it's different report
        that. This handles the case where LVM rounds a requested size
        up to a multiple of the extent size

    Returns:
      The final size of the logical volume, as a SizeString.
    Exceptions:
      CommandError: a logical volume command failed
    """
    lvSize = self.getSize()
    if not expected or lvSize != expected:
      self.log.debug(_("LVM set physical size to {0!s}").format(lvSize))

    slop = lvSize.toBytes() % blockSize
    if slop:
      newByteCount = lvSize.toBytes() - slop
      lvSize = SizeString(str(newByteCount) + 'B')
      self.reduce(lvSize)
      self.log.debug(_("Rounded physical size to {0!s}").format(lvSize))
    return lvSize

  def _physicalSizeCheck(self, physicalSize, forExtend):
    """Check the physical size requested for a create or extend operation
    against our supported maximum (if set). Raises an ArgumentError if
    the size is too large. In noRun mode, no check is made.

    Arguments:
      physicalSize (SizeString): The requested size. If None, the user
        is asking for all the space left in the volume group
      forExtend (bool): If True, this is an extend operation
    Exceptions:
      ArgumentError: requested size is not supported
    """
    if Command.noRunMode() or not self.maximumSize:
      return
    if physicalSize:
      if physicalSize > self.maximumSize:
        raise ArgumentError(_(
            "Requested physical size {sz} too large (maximum {mx})").format(
            sz=physicalSize, mx=self.maximumSize))
    else:
      physicalSize = self._vgFree()
      if forExtend:
        physicalSize += self.getSize()
      if physicalSize > self.maximumSize:
        raise ArgumentError(_(
            "Using all free space in {vg} too large (maximum {mx})").format(
            vg=self._volumeGroup, mx=self.maximumSize))

  def _vgFree(self):
    """Returns the free space in the volume group associated with this
    LogicalVolume.

    Returns:
      The size as a SizeString, zero-byte if an error occurred.
    """
    vgsCmd = Command(['vgs', '-o', 'vg_free', '--noheadings',
                      '--units', 'k', '--nosuffix', self._volumeGroup])
    kbytes = vgsCmd.runOutput().strip()
    if not kbytes:
      return SizeString('')
    return SizeString(kbytes + 'K')
