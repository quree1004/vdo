"""
  AlbireoService - manages Albireo servers and indexes

  Copyright (c) 2012-2014 Permabit Technology Corporation.
  @LICENSE@
  $Id: //eng/vdo-releases/nitrogen/src/c++/vdo/bin/vdomgmnt/AlbireoService.py#3 $

"""
from . import Brand, Command, CommandError, ArgumentError, Defaults
from . import Logger, LogicalVolume, Service, SizeString, Utils
import os


class AlbireoService(Service):
  """AlbireoService manages an Albireo index and server on the local node.

  Attributes:
    name (str): The name of this object; by convention, we use the
      URI 'dedupe://host:port'.
    cfreq (int): The checkpoint frequency.
    enabled (bool): If True, should be started by the `start` method.
    indexPath (str): Directory to be used for Albireo indexes.
    logicalVolume (LogicalVolume): The logical volume on which `indexPath`
      will be mounted.
    memory (str): The Albireo main memory setting.
    networkSpec (str): The Albireo service address, in the form host:port.
    size (SizeString): Size of the Albireo index.
    sparse (bool): If True, creates a sparse Albireo index.
    udsParallelFactor (int): Value for the UDS_PARALLEL_FACTOR environment
      variable used by albserver.
  """
  log = Logger.getLogger(Logger.myname + '.Service.AlbireoService')

  def __init__(self, name, **kw):
    Service.__init__(self, name)
    self.cfreq = kw.get('cfreq', Defaults.cfreq)
    self.enabled = kw.get('enabled', True)
    self.indexPath = kw.get('indexPath', '')
    logicalVolumePath = kw.get('logicalVolumePath', '')
    if logicalVolumePath:
      self.logicalVolume = LogicalVolume(logicalVolumePath)
    else:
      self.logicalVolume = None
    self.memory = kw.get('memory', Defaults.albireoMem)
    self.networkSpec = kw.get('networkSpec', '')
    self.size = kw.get('size', '')
    self.sparse = kw.get('sparse', Defaults.albireoSparse)
    self.udsParallelFactor = kw.get('udsParallelFactor',
                                    Defaults.udsParallelFactor)

  def __setattr__(self, name, value):
    if isinstance(value, str):
      if name in ['cfreq', 'udsParallelFactor']:
        object.__setattr__(self, name, int(value))
      elif name in ['enabled', 'sparse']:
        object.__setattr__(self, name, value[0].upper() == 'T')
      elif name in ['size']:
        object.__setattr__(self, name, SizeString(value))
      elif name in ['logicalVolumePath']:
        self.logicalVolume = LogicalVolume(value)
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
          obj="AlbireoService", attr=name))

  def __str__(self):
    return "AlbireoService(" + self.getName() + ")"

  def __repr__(self):
    lst = [self.__str__(), "["]
    lst.append(','.join('='.join([key, str(getattr(self, key))])
                        for key in self.__dict__ if not key.startswith('_')))
    lst.append("]")
    return "".join(lst)

  def create(self):
    """Creates an Albireo index."""
    self.log.announce(_("Creating Albireo index {0}").format(self._name))
    retval = self._createIndexDir()
    if retval != self.SUCCESS:
      return retval

    albireoDir = self.getAlbireoDir(self.indexPath)
    indexSpec = self.networkSpec + ':' + albireoDir
    albcreateBinary = Brand.map('albcreate')
    commandList = [albcreateBinary, '--index=' + albireoDir]
    if self.memory:
      commandList.append('--mem=' + str(self.memory))
    if self.sparse:
      commandList.append('--sparse')
    commandList.append('--cfreq=' + str(self.cfreq))
    createCmd = Command(commandList)
    try:
      createCmd()
      return self.SUCCESS
    except CommandError as ex:
      self.log.error(_("Could not create Albireo index {0}: {1!s}").format(
          indexSpec, ex))
      self.remove()
      return self.ERROR

  def remove(self):
    """Removes an Albireo index."""
    self.log.announce(_("Removing Albireo index {0}").format(self._name))
    if os.path.ismount(self.indexPath):
      umountCmd = Command(['umount', '-f', self.indexPath])
      try:
        umountCmd.waitFor(5)
      except CommandError as ex:
        self.log.error(_("Could not unmount Albireo index: {0!s}").format(ex))
        return self.ERROR
    rmCmd = Command(['rm', '-rf', self.indexPath])
    try:
      rmCmd()
      self.logicalVolume.remove()
      return self.SUCCESS
    except CommandError as ex:
      self.log.error(_("Could not remove Albireo index: {0!s}").format(
          ex))
      return self.ERROR

  def have(self):
    """Tests whether an Albireo index exists."""
    return os.path.exists(self.getAlbireoDir(self.indexPath))

  @staticmethod
  def createArgCheck(args):
    """Performs argument checks for creating an Albireo index.

    Arguments:
      args: the OptionParser options object
    Raises:
      ArgumentError
    """
    albireoIndexDir = Defaults.getAlbireoIndexDir(args)
    albireoDir = AlbireoService.getAlbireoDir(albireoIndexDir)
    if os.path.exists(albireoDir) and os.listdir(albireoDir):
      raise ArgumentError(_("Albireo index directory {dir} not empty").format(
          dir = albireoDir))

  def start(self, readyCmd = None):
    """Starts the Albireo server.

    Start is called when the VDO create and start commands are issued.
    In the case of create, we are starting a new albserver and thus
    want to generate an ERROR if the service does not come up promptly.
    In the case of start, we do not want to stall if the Albireo index
    needs to be rebuilt.

    Arguments:
    readyCmd -- if None, we are creating the service: return an ERROR
                if albserver does not come up within the timeout.
                if supplied, this command string should be passed to
                albserver with the --when-ready argument; an error will
                be returned only if the albserver command fails."""
    #pylint: disable=R0911
    self.log.announce(_("Starting Albireo server {0}").format(self._name))
    if not self.enabled:
      self.log.info(_("Albireo server {0} not enabled").format(self._name))
      return self.SUCCESS
    if self.running() and not Command.noRunMode():
      self.log.info(_("Albireo server {0} already started").format(self._name))
      return self.ALREADY
    albireoDir = self.getAlbireoDir(self.indexPath)
    indexSpec = self.networkSpec + ':' + albireoDir

    didMount = False
    if not os.path.ismount(self.indexPath):
      self.logicalVolume.setAvailable(True)
      mountCmd = Command(['mount', '-t', 'ext3', self.logicalVolume.fullpath(),
                          self.indexPath])
      try:
        mountCmd()
        didMount = True
      except CommandError as ex:
        self.log.error(_("Could not mount {0} on {1}: {2!s}").format(
            self.logicalVolume.fullpath(), self.indexPath, ex))
        return self.ERROR

    albserverBinary = Brand.map('albserver')
    albserverCmd = Command([albserverBinary, '--index=' + indexSpec,
                            '--daemon', '--pid-file=' + self._pidFilePath()])
    if readyCmd:
      albserverCmd.addArg('--when-ready=' + readyCmd)
    if self.udsParallelFactor != 0:
      albserverCmd.setenv('UDS_PARALLEL_FACTOR',
                          str(int(self.udsParallelFactor)))
    try:
      albserverCmd()
    except CommandError as ex:
      self.log.error(_("Could not start Albireo server {0}: {1!s}").format(
          self._name, ex))
      if didMount:
        Command(['umount', '-f', self.indexPath]).noThrowCall()
      return self.ERROR

    if not readyCmd:
      albpingBinary = Brand.map('albping')
      pingCmd = Command([albpingBinary, '--index=' + self.networkSpec])
      try:
        pingCmd.waitFor()
      except CommandError as e:
        self.log.error(_("Error starting Albireo server {0}: {1!s}").format(
            self._name, e))
        return self.ERROR
    return self.SUCCESS

  def stop(self):
    """Stops the Albireo server."""
    self.log.announce(_("Stopping Albireo server {0}").format(self._name))
    pid = self._getPid()
    if pid == 0 and not Command.noRunMode():
      self.log.info(_("Albireo server {0} already stopped").format(self._name))
      return self.ALREADY
    Utils.killProcess(pid)
    try:
      umountCmd = Command(['umount', '-f', self.indexPath])
      umountCmd.waitFor(5)
    except CommandError as ex:
      self.log.info(_("Albireo volume unmount failed: {0!s}").format(ex))
    return self.SUCCESS

  def running(self):
    """Returns True if the Albireo server is running."""
    pid = self._getPid()
    if pid == 0:
      return False
    return True

  @staticmethod
  def getKeys():
    """Returns the list of standard attributes for this object."""
    return ['cfreq', 'enabled', 'indexPath', 'logicalVolumePath', 'memory',
            'networkSpec', 'size', 'sparse', 'udsParallelFactor']

  def status(self, prefix):
    """Prints the status of this object to stdout."""
    print(prefix + "- " + self.getName() + ":")
    print(prefix + _("  Checkpoint frequency: {0}").format(self.cfreq))
    print(prefix + _("  Enabled: {0}").format(self.enabled))
    print(prefix + _("  Index directory: {0}").format(self.indexPath))
    print(prefix + _("  Index logical volume: {0}").format(
        self.logicalVolume))
    print(prefix + _("  Albireo server memory setting: {0}").format(
        self.memory))
    print(prefix + _("  Network spec: {0}").format(self.networkSpec))
    print(prefix + _("  Index size: {0}").format(self.size))
    print(prefix + _("  Sparse: {0}").format(self.sparse))
    print(prefix + _("  Server parallel factor: {0}").format(
        self.udsParallelFactor))
    if os.getuid() == 0:
      print(prefix + _("  System logical volume info: {0}").format(
          self.logicalVolume.status()))
    pid = self._getPid()
    if pid:
      print(prefix + _("  Server process ID: {0}").format(pid))
      albpingBinary = Brand.map('albping')
      Utils.statusHelper([albpingBinary, '--index=' + self.networkSpec],
                         prefix + _("  Server status: ") + os.linesep
                          + prefix + "    ")
    else:
      print(prefix + _("  Server process ID: (not running)"))

  @staticmethod
  def getAlbireoDir(indexPath):
    """Return the full path to the Albireo directory."""
    return os.path.join(indexPath, 'index-data')

  def _createIndexDir(self):
    """Creates a logical volume and directory for an Albireo index."""
    try:
      self.logicalVolume.create(4096, self.size)
    except CommandError as ex:
      self.log.error(_(
          "Can't create index logical volume {lv}: {ex}").format(
          lv=self.logicalVolume, ex=ex))
      return self.ERROR

    mkfsCmd = Command(['mkfs', '-t', 'ext3', self.logicalVolume.fullpath()])
    try:
      mkfsCmd()
    except CommandError as ex:
      self.log.error(_(
          "Could not make directory {0} for Albireo index: {1!s}").format(
          self.logicalVolume.fullpath(), ex))
      self.logicalVolume.remove(noThrow=True)
      return self.ERROR

    mkdirCmd = Command(['mkdir', '-p', self.indexPath])
    mountCmd = Command(['mount', '-t', 'ext3', self.logicalVolume.fullpath(),
                        self.indexPath])
    try:
      mkdirCmd()
      mountCmd()
    except CommandError as ex:
      self.log.error(_("Could not mount {0} on {1}: {2!s}").format(
          self.logicalVolume.fullpath(), self.indexPath, ex))
      self.logicalVolume.remove(noThrow=True)
      return self.ERROR

    Command(['chmod', '777', self.indexPath]).noThrowCall()
    return self.SUCCESS

  def _pidFilePath(self):
    """Returns the full path to the pid file for the Albireo server."""
    port = self.networkSpec.split(':')[1]
    albserverBinary = os.path.basename(Brand.map('albserver'))
    return '/var/run/{albserver}/{albserver}.{port}.pid'.format(
      albserver=albserverBinary, port=port)

  def _getPid(self):
    """Returns the process ID for the Albireo server or 0 if none."""
    try:
      f = open(self._pidFilePath(), 'r')
      pid = int(f.read().rstrip())
      f.close()
      os.kill(pid, 0)
      return pid
    except IOError:
      return 0
    except OSError:
      return 0
