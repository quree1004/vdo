"""
  KernelModuleService - manages the kvdo kernel module

  Copyright (c) 2012-2014 Permabit Technology Corporation.
  @LICENSE@
  $Id: //eng/vdo-releases/nitrogen/src/c++/vdo/bin/vdomgmnt/KernelModuleService.py#2 $

"""
from . import Brand, Command, CommandError, Defaults, Service
import string


class KernelModuleService(Service):
  """KernelModuleService manages the kvdo kernel module on the local node."""
  def __init__(self):
    Service.__init__(self, Brand.map('kvdo'))

  def __str__(self):
    return "KernelModuleService(\"{0}\")".format(self.getName())

  def __repr__(self):
    lst = [self.__str__(), "["]
    lst.append(','.join('='.join([key, str(getattr(self, key))])
                        for key in self.__dict__))
    lst.append("]")
    return "".join(lst)

  def start(self):
    """Loads the module if necessary."""
    modprobeCmd = Command(['modprobe', self._name])
    try:
      modprobeCmd()
      return self.SUCCESS
    except CommandError:
      return self.ERROR

  def stop(self):
    """Removes the module."""
    modprobeCmd = Command(['modprobe', '-r', self._name])
    try:
      modprobeCmd()
      return self.SUCCESS
    except CommandError:
      return self.ERROR

  def running(self, wait=True):
    """Returns True if the module is loaded and DM target is available."""
    lsmodCmd = Command(string.split("lsmod | grep -q '" + self._name + "'"))
    lsmodCmd.shell = True
    dmsetupCmd = Command(string.split("dmsetup targets | grep -q dedupe"))
    dmsetupCmd.shell = True
    try:
      if wait:
        lsmodCmd.waitFor()
        dmsetupCmd.waitFor()
      else:
        lsmodCmd()
        dmsetupCmd()
      return True
    except CommandError:
      return False

  def setLogLevel(self, level):
    """Sets the module log level."""
    if level != Defaults.vdoLogLevel:
      cmd = Command(string.split("echo" + level + " > /sys/"
                                 + self._name + "/log_level"))
      cmd.shell = True
      cmd.noThrowCall()

  def version(self):
    """Returns the module version as a string."""
    s = self._name + " "
    modinfo = Command(['modinfo', self._name]).runOutput()
    for line in modinfo.splitlines():
      if line.find('version') == 0:
        s += line
    return s

  def status(self, prefix):
    """Print the status of this object to stdout."""
    print(prefix + _("Kernel module:"))
    print(prefix + _("  Name: ") + self._name)
    print(prefix + _("  Loaded: ") + str(self.running(False)))
    print(prefix + _("  Version information: "))
    print(prefix +   "    " + self.version())
