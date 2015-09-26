"""
  Configuration - VDO manager configuration file handling

  Copyright (c) 2012-2013 Permabit Technology Corporation.
  @LICENSE@
  $Id: //eng/vdo-releases/nitrogen/src/c++/vdo/bin/vdomgmnt/Configuration.py#2 $

"""
from . import ArgumentError, AlbireoService, Command, Logger, VdoService
import os
import time
import xml.parsers.expat


class BadConfigVersionError(Exception):
  """Exception raised to indicate an error running a command."""
  def __init__(self, msg):
    super(BadConfigVersionError, self).__init__()
    self._msg = msg
  def __str__(self):
    return self._msg


class Configuration(object):
  """Configuration of VDO volumes and associated Albireo servers.

  This class is designed for use with the "with" statement. If
  Command.noRunMode is True, the file will still be opened and read
  but writes will not be performed.

  The Configuration is stored in a simple XML format; see
  vdoconfig.dtd.

  Attributes:
    _vdos: A dictionary of VDOServices, indexed by name.
    _albservers: A dictionary of AlbireoServices, indexed by URI.
    _filename: The name of the configuration file.
    _readonly: True iff this Configuration is read-only.
    _fh: The open file handle, or None if the file is not open.
    _dirty: True iff this Configuration has been modified but the
      changes have not been persisted.
    _mustExist: If True, the file must exist (otherwise a missing
      file is treated as an empty configuration).
    _deleteEmpty: If True, the `persist` method will delete the file
      if this Configuration is empty.
    _currsection, _currsecname, _currkey, _currvalue: State variables
      for the XML parser.
  """
  log = Logger.getLogger(Logger.myname + '.Configuration')
  supportedSchemaVersions = ["1.0"]

  def __init__(self, filename, readonly=True, mustExist=False,
               deleteEmpty=False):
    """Construct a Configuration.

    Args:
      filename (str): The path to the XML configuration file

    Kwargs:
      readonly (bool): If True, the configuration is read-only.
      mustExist (bool): If True, the configuration file must exist.
      deleteEmpty (bool): If True, the configuration file will be
        deleted when `persist` is called if the Configuration is
        empty.

    Raises:
      ArgumentError
    """
    self._vdos = {}
    self._albservers = {}
    self._filename = filename
    self._readonly = readonly
    self._fh = None
    self._dirty = False
    self._mustExist = mustExist
    self._deleteEmpty = deleteEmpty
    self._schemaVersion = "1.0"
    self._currsection = ''
    self._currsecname = ''
    self._currkey = ''
    self._currvalue = ''
    if self._mustExist and not os.path.exists(self._filename):
      raise ArgumentError(_("Configuration file {0} does not exist.").format(
          self._filename))

  def __enter__(self):
    mode = 'r'
    if not self._readonly:
      mode = 'a+'
    try:
      if os.path.exists(self._filename):
        self._fh = open(self._filename, mode)
        if os.path.getsize(self._filename) != 0:
          self._read()
      elif not self._readonly:
        self._fh = open(self._filename, mode)
    except IOError as (msg):
      raise ArgumentError(str(msg))
    return self

  def __exit__(self, exc_type, unused_exc_value, unused_traceback):
    if self._fh:
      self._fh.close()
      self._fh = None
    if exc_type:
      return False
    if self._deleteEmpty and self.empty():
      self._removeFile()
    return True

  def __repr__(self):
    """Returns a string representation of this object in YAML format."""
    s = "filename: " + repr(self._filename) + os.linesep
    s += "version: " + repr(self._schemaVersion) + os.linesep
    s += "vdos:" + os.linesep
    for vdo in self._vdos:
      s += "  - " + repr(self._vdos[vdo])
    s += os.linesep
    s += "albservers:" + os.linesep
    for alb in self._albservers:
      s += "  - " + repr(self._albservers[alb])
    return s

  def __str__(self):
    return "Configuration(" + self._filename + ")"

  def _read_startElement(self, name, attrs):
    """Function called by the XML parser when starting an element."""
    if self._currsection == '':
      if name == 'vdoconfig':
        self._schemaVersion = attrs['version']
        self.validateVersion(self._schemaVersion)
      elif name == 'vdo':
        self._currsection = name
        self._currsecname = attrs['name']
        self._currkey = ''
        self._currvalue = ''
        self._vdos[self._currsecname] = VdoService(self._currsecname)
      elif name == 'albserver':
        self._currsection = name
        self._currsecname = attrs['uri']
        self._currkey = ''
        self._currvalue = ''
        self._albservers[self._currsecname] = AlbireoService(self._currsecname)
    else:
      self._currkey = name
      self._currvalue = ''

  def _read_endElement(self, name):
    """Function called by the XML parser when ending an element."""
    if name == self._currsection:
      self._currsection = ''
    elif self._currkey != '':
      if self._currsection == 'vdo':
        setattr(self._vdos[self._currsecname], self._currkey, self._currvalue)
      elif self._currsection == 'albserver':
        setattr(self._albservers[self._currsecname], self._currkey,
                self._currvalue)
    self._currkey = ''
    self._currvalue = ''

  def _read_charData(self, data):
    """Function called by the XML parser when reading character data."""
    self._currvalue = data

  def _read(self):
    """Reads in a Configuration from a file."""
    assert self._fh, "Configuration._read called without an open file"
    self.log.debug("Reading configuration from {0}".format(self._filename))
    self._fh.seek(0)
    self._currsection = ''
    self._currsecname = ''
    self._currkey = ''
    self._currvalue = ''
    p = xml.parsers.expat.ParserCreate()
    p.returns_unicode = False
    p.StartElementHandler = self._read_startElement
    p.EndElementHandler = self._read_endElement
    p.CharacterDataHandler = self._read_charData
    p.buffer_text = True
    p.ParseFile(self._fh)
    self._dirty = False
    return 0

  @classmethod
  def validateVersion(cls, ver):
    """Checks a configuration file schema version string against the list
    of supported schemas.

    Args:
      ver (str): the schema version string to check

    Raises:
      BadConfigVersionError: version not supported.
    """
    if ver not in cls.supportedSchemaVersions:
      raise BadConfigVersionError(_(
          "Configuration file version {v} not supported").format(v=ver))

  def persist(self):
    """Writes out the Configuration if necessary.

    If the Configuration is read-only or has not been modified, this
    method will silently return. If Command.noRunMode is True, any
    new Configuration will be printed to stdout instead of the file.

    This method will generate an assertion failure if the configuration
    file is not open.
    """
    assert self._fh, "Configuration._persist called without an open file"
    if self._readonly:
      return
    if not self._dirty:
      self.log.debug("Configuration is clean, not persisting")
      return
    self.log.debug("Writing configuration to {0}".format(self._filename))
    if (os.path.isfile(self._filename)):
      cpCmd = Command(["cp", self._filename, self._filename + ".bak"])
      cpCmd.noThrowCall()

    conf = []
    conf.append("<?xml version=\"1.0\" encoding=\"UTF-8\" ?>")
    conf.append("<!DOCTYPE vdoconfig SYSTEM \"vdoconfig.dtd\">")
    conf.append("<vdoconfig version=\"" + self._schemaVersion + "\">")
    for vdo in self._vdos:
      conf.append("  <vdo name=\"" + vdo + "\">")
      for key in self._vdos[vdo].getKeys():
        value = getattr(self._vdos[vdo], key)
        conf.append("    <" + key + ">" + str(value) + "</" + key + ">")
      conf.append("  </vdo>")
    for alb in self._albservers:
      conf.append("  <albserver uri=\"" + alb + "\">")
      for key in self._albservers[alb].getKeys():
        value = getattr(self._albservers[alb], key)
        conf.append("    <" + key + ">" + str(value) + "</" + key + ">")
      conf.append("  </albserver>")
    conf.append("</vdoconfig>")
    conf.append("")
    s = os.linesep.join(conf)
    if not Command.noRunMode():
      self._fh.seek(0)
      self._fh.truncate()
      self._fh.write(s)
      self._fh.flush()
      os.fsync(self._fh)
    else:
      print(_("New configuration (not written):"))
      print(s)
    self._dirty = False

  def _assertCanModify(self):
    """Asserts that mutative operations are allowed on this object."""
    assert self._fh, "Configuration not open"
    assert not self._readonly, "Configuration is read-only"

  def addVdo(self, name, vdo, replace=False):
    """Adds or replaces a VdoService object in the configuration.
    Generates an assertion error if this object is read-only.

    Arguments:
    name -- name of the VdoService
    vdo -- the VdoService to add or replace
    replace -- if True, any existing VdoService will be replaced
    Returns: False if the VdoService exists and replace is False,
      True otherwise
    """
    self._assertCanModify()
    self.log.debug("Adding vdo \"{0}\" to configuration".format(name))
    if not replace and self.haveVdo(name):
      return False
    self._vdos[name] = vdo
    self._dirty = True
    return True

  def addAlbserver(self, name, albserver, replace=False):
    """Adds or replaces a AlbireoService object in the configuration.
    Generates an assertion error if this object is read-only.

    Arguments:
    name -- name of the AlbireoService
    vdo -- the AlbireoService to add or replace
    replace -- if True, any existing AlbireoService will be replaced
    Returns: False if the AlbireoService exists and replace is False,
      True otherwise
    """
    self._assertCanModify()
    self.log.debug("Adding albserver \"{0}\" to configuration".format(name))
    if not replace and self.haveAlbserver(name):
      return False
    self._albservers[name] = albserver
    self._dirty = True
    return True

  def empty(self):
    """Returns True if this configuration is empty."""
    return len(self._vdos) == 0 and len(self._albservers) == 0

  def haveVdo(self, name):
    """Returns True if we have a VDO with a given name."""
    return name in self._vdos

  def haveAlbserver(self, name):
    """Returns True if we have an albserver with a given name."""
    return name in self._albservers

  def getVdo(self, name):
    """Retrieves a VDO by name."""
    return self._vdos[name]

  def getAlbserver(self, name):
    """Retrieves an albserver by name."""
    return self._albservers[name]

  def getAllVdos(self):
    """Retrieves a list of all known VDOs."""
    return self._vdos

  def getAllAlbservers(self):
    """Retrieves a list of all known albservers."""
    return self._albservers

  def removeVdo(self, name):
    """Removes a VDO by name."""
    self._assertCanModify()
    del self._vdos[name]
    self._dirty = True

  def removeAlbserver(self, name):
    """Removes an albserver by name."""
    self._assertCanModify()
    del self._albservers[name]
    self._dirty = True

  def listAllVdos(self):
    """Retrieves a list of the names of all known VDOs."""
    return sorted(self._vdos.keys())

  def listAllAlbservers(self):
    """Retrieves a list of the names of all known albservers."""
    return sorted(self._albservers.keys())

  def status(self, prefix):
    """Prints information displayed by the 'status' command to stdout.

    Args:
      prefix (str): A string to print before every line.
    """
    from stat import ST_MTIME
    print(prefix + "Configuration:")
    print(prefix + "  File: " + self._filename)
    try:
      st = os.stat(self._filename)
      print(prefix + _("  Last modified: ") +
            time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st[ST_MTIME])))
    except IOError:
      print(prefix + _("  Last modified: not available"))

  def _removeFile(self, backup=False):
    """Deletes the current configuration file and optionally its backup.
    In noRun mode, pretend that we're doing an rm of the file."""
    if Command.noRunMode():
      dummyCmd = Command(['rm', self._filename])
      dummyCmd()
      return
    if os.path.exists(self._filename):
      os.remove(self._filename)
    if backup:
      bak = self._filename + ".bak"
      if os.path.exists(bak):
        os.remove(bak)
