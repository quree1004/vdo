"""
  Extension - superclass for VDO manager extensions

  Copyright (c) 2013 Permabit Technology Corporation.
  @LICENSE@
  $Id: //eng/vdo-releases/nitrogen/src/c++/vdo/bin/vdomgmnt/extensions/Extension.py#1 $

"""


class Extension(object):
  """Abstract superclass for extensions.

  Attributes:
    desc (str): short description of the extension
    version (str): version string
    protocolList (list of str): supported protocols
  """
  desc = "Abstract superclass for extensions"
  version = "0.1"
  protocolList = []

  def __init__(self):
    pass

  def __str__(self):
    return "Extension"

  def __call__(self, caller, protocol, operation):
    """Method called at each extension point. All known extensions
    will be called in arbitrary order; subclasses of Extension should
    use the protocol and operation arguments to decide how to react.

    Arguments:
      caller (object): the owner of the extension point
      protocol (str): the extension protocol
      operation (str): the operation
    """
    pass

  def prepare(self, parser, vdoHelp):
    """Function called at VDO manager startup before argument
    parsing has been done. Used for adding arguments and help.

    Arguments:
      parser (OptionParser): the command line option parser
      vdoHelp (class): the VdoHelp class
    """
    pass

  def configure(self, options):
    """Function called at VDO manager startup after argument
    parsing has been done. Used for configuring the extension.

    Arguments:
      options (OptionParser): command line arguments
    """
    pass
