"""
  Extensions - manage extensions for the VDO manager

  Copyright (c) 2013 Permabit Technology Corporation.
  @LICENSE@
  $Id: //eng/vdo-releases/nitrogen/src/c++/vdo/bin/vdomgmnt/Extensions.py#1 $

"""
from . import Logger
#pylint: disable=W0401
#pylint: disable=W0614
import inspect
import sys


class Extensions(object):
  """Extensions manages extensions to the VDO manager, either
  separately licensed features or user-developed plugins.

  For testing, extensions may be disabled using the vdo manager's
  --disableExtensions=<list> option, where <list> is a comma-separated
  list of extensions to ignore. Non-existent extensions in this list
  are silently ignored. The special value "all" disables all
  extensions. Note that disabled extensions will still be instantiated
  (since this happens before argument processing is done); the list is
  pruned in the configure method.
  """
  log = Logger.getLogger(Logger.myname + '.Extensions')
  instance = None
  moduleName = 'vdomgmnt.extensions'

  def __init__(self):
    self._classList = []
    self._objList = []
    self._populate()

  def __str__(self):
    "Extensions"

  def __repr__(self):
    lst = ["Extensions["]
    lst.append(','.join('='.join([key, str(getattr(self, key))])
                        for key in self.__dict__))
    lst.append("]")
    return "".join(lst)

  def __call__(self, caller, protocol, op):
    unused_list = [k(caller, protocol, op) for k in self._classList]

  def _populate(self):
    """Populate the class list with all extensions found. Can be
    called multiple times to reload the class list; this will also
    clear the list of active objects."""
    import vdomgmnt.extensions
    self._classList = []
    self._objList = []
    for name, klass in inspect.getmembers(sys.modules[self.moduleName],
                                          inspect.isclass):
      if name != 'Extension':
        self._classList.append(klass())

  def doPrepare(self, parser, vdoHelp):
    """Calls the prepare method on all registered extensions."""
    unused_list = [k.prepare(parser, vdoHelp) for k in self._classList]

  def doConfigure(self, options):
    """Calls the confiugure method on all registered extensions."""
    if options.disableExtensions == "all":
      self._classList = []
    else:
      excludeList = options.disableExtensions.split(',')
      self._classList = [k for k in self._classList
                         if k.__class__.__name__ not in excludeList]
    unused_list = [k.configure(options) for k in self._classList]

  def doListExtensions(self, verbose):
    """List all loaded extensions."""
    for k in self._classList:
      print("{0:<14} {1:<4}  loaded  {2}".format(str(k), k.version, k.desc))
      if verbose:
        print "        protocols: " + ','.join(k.protocolList)

  @classmethod
  def extensionPoint(cls, caller, protocol, op):
    """Calls all known extensions."""
    cls.instance(caller, protocol, op)

  @classmethod
  def init(cls):
    """Instantiates a class-scope Extensions object."""
    cls.instance = Extensions()

  @classmethod
  def prepare(cls, parser, vdoHelp):
    """Calls the prepare method on the class-scope instance."""
    cls.instance.doPrepare(parser, vdoHelp)

  @classmethod
  def configure(cls, options):
    """Calls the configure method on the class-scope instance."""
    cls.instance.doConfigure(options)

  @classmethod
  def listExtensions(cls, verbose=False):
    """Calls the list extensions method on the class-scope instance."""
    cls.instance.doListExtensions(verbose)
