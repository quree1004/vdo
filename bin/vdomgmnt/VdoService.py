"""
  VdoService - manages the VDO service on the local node

  Copyright (c) 2012-2013 Permabit Technology Corporation.
  @LICENSE@
  $Id: //eng/vdo-releases/nitrogen/src/c++/vdo/bin/vdomgmnt/VdoService.py#13 $

"""
from . import Brand, Command, CommandError, Defaults
from . import Extensions, KernelModuleService, Logger, LogicalVolume
from . import Service, SizeString, Utils
import os
import re
import time


class VdoService(Service):
  """VdoService manages a vdo device mapper target on the local node.

  Attributes:
    blockMapCacheSize (sizeString): Memory allocated for block map pages.
    blockMapPageSize (int): Size of block map pages in bytes.
    enableCompression (bool): If True, compression should be
      enabled on this volume the next time the `start` method is run.
    enableDeduplication (bool): If True, deduplication should be
      enabled on this volume the next time the `start` method is run.
    enabled (bool): If True, should be started by the `start` method.
    logicalSize (SizeString): The logical size of this VDO volume.
    logicalVolume (LogicalVolume): The logical volume used for backing
      storage for this VDO volume.
    mdRaid5Mode (str): on or off.  Enables performance
      optimizations for MD RAID5 storage configurations.
    physicalSize (SizeString): The physical size of this VDO volume.
    readCacheSize (SizeString): The size of the read cache, in addition
      to a minimum set by the VDO software.
    recoveryScanRate (int): The rate of block map scanning in recovery mode.
    recoverySweepRate (int): The rate of slab sweeping in recovery mode.
    reserveSize (SizeString): The size of the recovery reserve.
    server (str): Name of the AlbireoService object used by this
      VDO volume.
    writePolicy (str): sync, async, or read_from_superblock.
  """
  log = Logger.getLogger(Logger.myname + '.Service.VdoService')

  # Key values to use accessing a dictionary created via yaml-loading the
  # output of vdo status.

  # Access the VDO list.
  vdosKey = "VDOs"

  # Access the per-VDO info.
  vdoBlockMapCacheSizeKey = _("Block map cache size")
  vdoBlockMapPageSizeKey = _("Block map page size")
  vdoBlockSizeKey = _("Block size")
  vdoCompressionEnabledKey = _("Enable compression")
  vdoDeduplicationEnabledKey = _("Enable deduplication")
  vdoReadCacheSizeKey = _("Read cache size")
  vdoLogicalSizeKey = _("Logical size")
  vdoMdRaid5ModeKey = _("MD RAID5 mode")
  vdoPhysicalSizeKey = _("Physical size")
  vdoPhysicalThreadsKey = _("Physical threads")
  vdoStatisticsKey = _("VDO statistics")
  vdoWritePolicyKey = _("Configured write policy")

  def __init__(self, name, **kw):
    Service.__init__(self, name)
    self.physicalBlockSize = Defaults.vdoPhysicalBlockSize
    self.logicalBlockSize = self.physicalBlockSize

    self.blockMapCacheSize = kw.get('blockMapCacheSize',
                                    Defaults.blockMapCacheSize)
    self.blockMapPageSize = kw.get('blockMapPageSize',
                                   Defaults.blockMapPageSize)
    if kw.get('enable512e', Defaults.enable512e):
      self.logicalBlockSize = 512
    self.enableCompression = kw.get('enableCompression', False)
    self.enableDeduplication = kw.get('enableDeduplication', True)
    self.enabled = kw.get('enabled', True)
    self.logicalSize = kw.get('logicalSize', '')
    logicalVolumePath = kw.get('logicalVolumePath', '')
    if logicalVolumePath:
      self.logicalVolume = LogicalVolume(logicalVolumePath)
      self.logicalVolume.maximumSize = SizeString("256T")
    else:
      self.logicalVolume = None
    self.mdRaid5Mode = kw.get('mdRaid5Mode', Defaults.mdRaid5Mode)
    self.physicalSize = kw.get('physicalSize', '')
    self.readCacheSize = kw.get('readCacheSize', Defaults.readCacheSize)
    self.recoveryScanRate = kw.get('recoveryScanRate',
                                   Defaults.recoveryScanRate)
    self.recoverySweepRate = kw.get('recoverySweepRate',
                                    Defaults.recoverySweepRate)
    self.reserveSize = kw.get('reserveSize', Defaults.reserveSize)
    self.server = kw.get('server', '')
    self.writePolicy = kw.get('writePolicy', Defaults.configuredWritePolicy)

  def __setattr__(self, name, value):
    if isinstance(value, str):
      if name in ['blockMapPageSize', 'logicalBlockSize', 'physicalBlockSize',
                  'recoveryScanRate', 'recoverySweepRate']:
        object.__setattr__(self, name, int(value))
      elif name in ['enableCompression', 'enableDeduplication', 'enabled']:
        object.__setattr__(self, name, value[0].upper() == 'T')
      elif name in ['blockMapCacheSize', 'logicalSize', 'physicalSize',
                    'readCacheSize', 'reserveSize']:
        object.__setattr__(self, name, SizeString(value))
      elif name in ['logicalVolumePath']:
        self.logicalVolume = LogicalVolume(value)
        self.logicalVolume.maximumSize = SizeString("256T")
      else:
        object.__setattr__(self, name, value)
    else:
      object.__setattr__(self, name, value)

  def __getattr__(self, name):
    # Fake this attribute so we don't have to make incompatible
    # changes to the configuration file format.
    if name in ['logicalVolumePath']:
      return self.logicalVolume.fullpath()
    else:
      raise AttributeError("'{obj}' object has no attribute '{attr}'".format(
          obj="VdoService", attr=name))

  def __str__(self):
    return "VdoService(" + self.getName() + ")"

  def __repr__(self):
    lst = [self.__str__(), "("]
    lst.append(','.join('='.join([key, str(getattr(self, key))])
                        for key in self.__dict__ if not key.startswith('_')))
    lst.append(")")
    return "".join(lst)

  def create(self):
    """Creates a VDO target."""
    self.log.announce(_("Creating VDO device {0}").format(self.getName()))
    try:
      self.physicalSize = self.logicalVolume.create(self.physicalBlockSize,
                                                    self.physicalSize)
    except CommandError as ex:
      self.log.error(_("Can't create logical volume {lv}: {ex}").format(
          lv=self.logicalVolume, ex=ex))
      return self.ERROR

    if not self.logicalSize:
      self.logicalSize = self.physicalSize
    self.logicalSize.round(self.physicalBlockSize)
    try:
      self._formatTarget()
      return self.SUCCESS
    except CommandError as ex:
      self.log.error(ex)
      self.logicalVolume.remove(noThrow=True)
      return self.ERROR

  def remove(self):
    """Removes a VDO target."""
    self.log.announce(_("Removing VDO volume {0}").format(self.getName()))
    self.logicalVolume.remove(noThrow=True)
    return self.SUCCESS

  def have(self):
    """Returns True if a VDO target exists."""
    return self.logicalVolume.exists()

  def start(self, networkSpec, rebuildStatistics=False, forceRebuild=False):
    """Starts the VDO target mapper. In noRun mode, we always assume
    the service is not yet running."""
    self.log.announce(_("Starting VDO service {0}").format(self.getName()))
    if not self.enabled:
      self.log.info(_("VDO service {0} not enabled").format(self.getName()))
      return self.SUCCESS
    if self.running() and not Command.noRunMode():
      self.log.info(_("VDO service {0} already started").format(
          self.getName()))
      return self.ALREADY
    numSectors = self.logicalSize.toSectors()
    kms = KernelModuleService()
    if kms.start() == self.ERROR:
      return self.ERROR
    self.logicalVolume.setAvailable(True)
    numericSpec = self._makeNetworkSpecNumeric(networkSpec)
    vdoConf = " ".join(["0", str(numSectors), "dedupe",
                        self.logicalVolume.fullpath(),
                        str(self.physicalBlockSize),
                        str(self.logicalBlockSize),
                        str(self.readCacheSize.toBytes()
                            // self.physicalBlockSize),
                        str(self.recoveryScanRate),
                        str(self.recoverySweepRate),
                        self.mdRaid5Mode,
                        self.writePolicy,
                        self._name, numericSpec])
    dmsetupCmd = Command(["dmsetup", "create", self._name, "--table", vdoConf])
    try:
      if rebuildStatistics:
        self._rebuildStatistics()
      else:
        try:
          if forceRebuild:
            self._forceRebuild()
        except CommandError:
          self.log.error(_("Device {0} not read-only").format(self.getName()))
          return self.ERROR
      dmsetupCmd()
      try:
        if self.enableCompression:
          Extensions.extensionPoint(self, "Compression", "on")
      except CommandError:
        self.log.error(_("Could not enable compression for {0}").format(
            self.getName()))
        return self.ERROR
      return self.SUCCESS
    except CommandError:
      self.log.error(_("Could not set up device mapper for {0}").format(
          self.getName()))
      return self.ERROR

  def stop(self, force=False):
    """Stops the VDO target mapper. In noRun mode, assumes the service
    is already running."""
    self.log.announce(_("Stopping VDO service {0}").format(self.getName()))
    if not self.running() and not Command.noRunMode():
      self.log.info(_("VDO service {0} already stopped").format(
          self.getName()))
      return self.ALREADY

    if self._hasMounts():
      if force:
        umountCmd = Command(["umount", "-f", self.getPath()])
        umountCmd.noThrowCall()
      else:
        self.log.error(_("cannot stop VDO volume with mounts {0}").format(
            self.getName()))
        return self.ERROR

    time.sleep(1)
    try:
      dmsetupCmd = Command(["dmsetup", "remove", self.getName()])
      dmsetupCmd()
      return self.SUCCESS
    except CommandError:
      self.log.error(_("cannot stop VDO service {0}").format(
          self.getName()))
      return self.ERROR

  def running(self):
    """Returns True if the VDO service is available."""
    cmd = Command(["dmsetup", "status", self.getName()])
    try:
      cmd()
      return True
    except CommandError:
      return False

  @staticmethod
  def getKeys():
    """Returns the list of standard attributes for this object."""
    return ["blockMapCacheSize", "blockMapPageSize",
            "enableCompression", "enableDeduplication", "enabled",
            "logicalBlockSize", "logicalSize", "logicalVolumePath",
            "mdRaid5Mode", "physicalBlockSize", "physicalSize",
            "readCacheSize", "recoveryScanRate", "recoverySweepRate",
            "reserveSize", "server", "writePolicy"]

  def status(self, prefix):
    """Prints the status of this object to stdout."""
    print(prefix + "- " + self.getName() + ":")

    print(prefix + "  {0}: {1}".format(self.vdoBlockMapCacheSizeKey,
                                       self.blockMapCacheSize))
    print(prefix + "  {0}: {1}".format(self.vdoBlockMapPageSizeKey,
                                       self.blockMapPageSize))
    print(prefix + "  {0}: {1}".format(self.vdoBlockSizeKey,
                                       self.physicalBlockSize))
    if self.logicalBlockSize == 512:
      print(prefix + _("  512 byte emulation: on"))
    else:
      print(prefix + _("  512 byte emulation: off"))
    print(prefix + "  {0}: {1}".format(self.vdoReadCacheSizeKey,
                                       self.readCacheSize))
    print(prefix + _("  Recovery scan rate: {0}").format(
        self.recoveryScanRate))
    print(prefix + _("  Recovery sweep rate: {0}").format(
        self.recoverySweepRate))
    print(prefix + _("  Recovery reserve size: {0}").format(self.reserveSize))
    print(prefix + "  {0}: {1}".format(self.vdoCompressionEnabledKey,
                                       self.enableCompression))
    print(prefix + "  {0}: {1}".format(self.vdoDeduplicationEnabledKey,
                                       self.enableDeduplication))
    print(prefix + _("  Enabled: {0}").format(str(self.enabled)))
    print(prefix + "  {0}: {1}".format(self.vdoLogicalSizeKey,
                                       self.logicalSize))
    print(prefix + _("  Logical volume path: {0}").format(
        self.logicalVolume.fullpath()))
    print(prefix + "  {0}: {1}".format(self.vdoMdRaid5ModeKey,
                                       self.mdRaid5Mode))
    print(prefix + "  {0}: {1}".format(self.vdoPhysicalSizeKey,
                                       self.physicalSize))
    print(prefix + _("  Server: {0}").format(self.server))
    print(prefix + "  {0}: {1}".format(self.vdoWritePolicyKey,
                                       self.writePolicy))
    if os.getuid() == 0:
      print(prefix + _("  System volume group info: {0}").format(
          self.logicalVolume.vgStatus()))
      print(prefix + _("  System logical volume info: {0}").format(
          self.logicalVolume.status()))
      Utils.statusHelper(['dmsetup', 'status', self.getName()],
                         prefix + _("  Device mapper status: "))
      try:
        vdoStatsBinary = Brand.map('vdoStats')
        cmd = Command([vdoStatsBinary, '--verbose', self.getPath()])
        cmd()
        print(prefix + "  {0}: ".format(self.vdoStatisticsKey))
        self._printPrefixed(cmd.stdout, prefix + '    ')
      except CommandError:
        print(prefix + "  {0}: {1}".format(self.vdoStatisticsKey,
                                           _("not available")))
      return 0

  def growPhysical(self, newPhysicalSize=None):
    """Grows the physical size of this VDO volume.

    Arguments:
      newPhysicalSize (SizeString): The new size. If None, use all the
                                    remaining free space in the volume
                                    group.
    Returns:
      0 for success, 1 for error
    """
    try:
      newLvSize = self.logicalVolume.extend(self.physicalBlockSize,
                                            newPhysicalSize)
    except CommandError as ex:
      self.log.error(_("Can't extend logical volume {lv}: {ex}").format(
          lv=self.logicalVolume, ex=ex))
      return 1

    try:
      suspendCmd = Command(["dmsetup", "suspend", self.getName()])
      suspendCmd()
    except CommandError as ex:
      self.log.error(_("Can't suspend VDO volume {0}: {1!s}").format(
          self.getName(), ex))
      self.logicalVolume.reduce(self.physicalSize)
      return 1

    retval = 1
    logicalBlocks = self.logicalSize.toBytes() / int(self.physicalBlockSize)
    physicalBlocks = newLvSize.toBytes() / int(self.physicalBlockSize)
    reconfigCmd = Command(['dmsetup', 'message', self.getName(), '0',
                           'reconfigure', str(self.physicalBlockSize),
                           str(logicalBlocks), str(physicalBlocks)])
    try:
      reconfigCmd()
      self.physicalSize = newLvSize
      retval = 0
    except CommandError as (msg):
      self.log.error(msg)
    finally:
      resumeCmd = Command(["dmsetup", "resume", self.getName()])
      try:
        resumeCmd()
      except CommandError:
        self.log.error(_("Could not resume {0}").format(self.getName()))
        return 1

    if retval != 0:
      self.logicalVolume.reduce(self.physicalSize)

    return retval

  def getPath(self):
    """Returns the full path to this VDO device."""
    return os.path.join("/dev/mapper", self.getName())

  def _hasMounts(self):
    """Tests whether filesystems are mounted on the VDO device.

    Returns:
      True iff the VDO device has something mounted on it.
    """
    mountCmd = Command(['mount'])
    mountList = mountCmd.runOutput()
    if mountList:
      matcher = re.compile(r'(\A|\s+)' + re.escape(self.getPath()) + r'\s+')
      for line in mountList.splitlines():
        if matcher.search(line):
          return True
    return False

  @staticmethod
  def _printPrefixed(s, prefix):
    """Print a block of text, prefixing each line with a string."""
    for line in s.splitlines():
      print(prefix + line)

  def _formatTarget(self):
    """Formats the VDO target."""
    logicalSize = self.logicalSize.asInteger()
    physicalSize = self.physicalSize.asInteger()
    vdoformatBinary = Brand.map('vdoformat')
    formatCmd = Command([vdoformatBinary,
                         "--logical-size=" + str(logicalSize),
                         "--physical-size=" + str(physicalSize)])
    if self.blockMapCacheSize != Defaults.blockMapCacheSize:
      formatCmd.addArg("--block-map-cache-size=" + str(self.blockMapCacheSize))
    if self.blockMapPageSize != Defaults.blockMapPageSize:
      formatCmd.addArg("--block-map-page-size=" + str(self.blockMapPageSize))
    if self.reserveSize != Defaults.reserveSize:
      formatCmd.addArg("--recovery-reserve-size=" + str(self.reserveSize))
    formatCmd.addArg(self.logicalVolume.fullpath())
    formatCmd()

  def _rebuildStatistics(self):
    """Calls vdoformat to rebuild statistics at next start."""
    logicalSize = self.logicalSize.asInteger()
    vdoformatBinary = Brand.map('vdoformat')
    vdoformatCmd = Command([vdoformatBinary, "--rebuild-statistics",
                            "--logical-size=" + str(logicalSize),
                            self.logicalVolume.fullpath()])
    vdoformatCmd()

  def _forceRebuild(self):
    """Calls vdoformat to exit read-only mode and force a metadata
    rebuild at next start."""
    logicalSize = self.logicalSize.asInteger()
    vdoformatBinary = Brand.map('vdoformat')
    vdoformatCmd = Command([vdoformatBinary, "--force-rebuild",
                            "--logical-size=" + str(logicalSize),
                            self.logicalVolume.fullpath()])
    vdoformatCmd()

  @staticmethod
  def _makeNetworkSpecNumeric(networkSpec):
    """Given a network spec with a possibly non-numeric host part,
    convert it to a network spec with a dotted-quad IP address."""
    from socket import gethostbyname
    host, port = networkSpec.split(':')
    return gethostbyname(host) + ':' + port
