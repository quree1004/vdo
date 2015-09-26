"""
  Brand - manages VDO manager branding

  Copyright (c) 2013 Permabit Technology Corporation.
  @LICENSE@
  $Id: //eng/vdo-releases/nitrogen/src/c++/vdo/bin/vdomgmnt/Brand.py#1 $

"""
from . import Logger
import logging
import os
import xml.parsers.expat

class Brand(object):
  """Brand manages VDO manager rebranding, mapping Permabit executable
  names. Uses an XML customization file to define mappings.

  All the data managed by this object is set by the read() method;
  once it completes, accessing the data will not generate exceptions.

  Attributes:
    _currsection (str): for parsing, current section being processed
    _currkey (str): for parsing, current map key
    _currvalue (str): for parsing, current character data
    _customFile (str): a customization file; need not exist
    _cmdMap (dict): holds command name mappings

  """
  log = logging.getLogger(Logger.myname + '.Brand')
  instance = None

  def __init__(self, customFile):
    self._currsection = ''
    self._currkey = ''
    self._currvalue = ''
    self._customFile = customFile
    self._cmdMap = {}

  def __str__(self):
    return "Brand(\"{0}\")".format(self._customFile)

  def __repr__(self):
    lst = [self.__str__(), "["]
    lst.append(','.join('='.join([key, str(getattr(self, key))])
                        for key in self.__dict__))
    lst.append("]")
    return "".join(lst)

  def clear(self):
    """Clears all the data in this object."""
    self._cmdMap.clear()
    self._currsection = ''
    self._currkey = ''
    self._currvalue = ''

  def _read_startElement(self, name, unused_attrs):
    """Function called by the XML parser when starting an element."""
    if name == 'command' or name == 'default':
      self._currsection = name
      self._currkey = ''
      self._currvalue = ''

  def _read_endElement(self, name):
    """Function called by the XML parser when ending an element."""
    if name == self._currsection:
      self._currsection = ''
      self._currkey = ''
      self._currvalue = ''
    elif self._currsection == 'command':
      if name == 'internalName':
        self._currkey = self._currvalue
      elif name == 'visibleName':
        self._cmdMap[self._currkey] = self._currvalue

  def _read_charData(self, data):
    """Function called by the XML parser when reading character data."""
    self._currvalue = data

  def read(self):
    """Reads in the customization file. If the file does not exist,
    no mapping will be done; this does not generate an error, but
    a message will be logged at WARN level. If an XML error is
    encountered, no mapping will be done, and a message will be
    logged at ERROR level.

    This function may be called repeatedly; it will reset all data
    and re-read the customization file each time.
    """
    self.clear()
    if not os.path.exists(self._customFile):
      self.log.warn(_("Customization file {0} not found, not mapping").format(
          self._customFile))
      return

    try:
      with open(self._customFile, 'r') as fh:
        self.log.debug("Reading customization file {0}".format(
            self._customFile))
        p = xml.parsers.expat.ParserCreate()
        p.returns_unicode = False
        p.StartElementHandler = self._read_startElement
        p.EndElementHandler = self._read_endElement
        p.CharacterDataHandler = self._read_charData
        p.buffer_text = True
        p.ParseFile(fh)
        return
    except xml.parsers.expat.ExpatError as ex:
      self.log.error("{0}: {1}".format(self._customFile, ex))
    except IOError as ex:
      self.log.error(ex)
    except OSError as ex:
      self.log.error(ex)
    self.clear()

  def mapCommand(self, cmdName):
    """Maps a command name, returning the mapped value. If the
    command name is not known, returns it unchanged.

    Arguments:
      cmdName (str): the command name to map.
    Returns:
      The command name, mapped if necessary.
    """
    if cmdName in self._cmdMap:
      return self._cmdMap[cmdName]
    return cmdName

  @classmethod
  def init(cls, customFile):
    """Initialize a class-scope Brand instance.

    Arguments:
      customFile (str): path to the customization file
    """
    cls.instance = Brand(customFile)
    cls.instance.read()

  @classmethod
  def map(cls, cmdName):
    """Map a command name using the class-scope Brand instance.
    Returns its argument if the instance has not been initialized.

    Arguments:
      cmdName (str): the command name to map
    """
    if cls.instance:
      return cls.instance.mapCommand(cmdName)
    return cmdName
