"""
  Service - Abstract superclass for services

  Copyright (c) 2012-2013 Permabit Technology Corporation.
  @LICENSE@
  $Id: //eng/vdo-releases/nitrogen/src/c++/vdo/bin/vdomgmnt/Service.py#1 $

"""
from . import Logger


class Service(object):
  """Superclass for services.

  Every subclass of Service controls a service (such as an Albireo
  index or a VDO target) managed by this command. The create/remove/
  have methods are one-time operations that do things like 'albcreate'
  that are persistent, while start/stop/running are used to control
  the availability of the service, either manually or automatically at
  system boot and shutdown. The control commands are idempotent, and
  return values specified as exit codes for /etc/init.d scripts
  specified in the LSB.

  Methods:
    getName  (method on Service) returns a name for the object
    create   creates the service; done once, paired with 'remove'
    remove   removes the service
    have     returns True if the service has been created
    start    starts the service; idempotent; run at system boot
    stop     stops the service; idempotent; run at shutdown
    running  returns True if the service is running
    getKeys  returns a list of the keys to be stored in the
             configuration file
    status   returns the status of the service in YAML format
  Return codes:
    0        (self.SUCCESS) success
    1        (self.ALREADY) idempotent command did nothing
    2        (self.ERROR) error(s) occurred
  """
  log = Logger.getLogger(Logger.myname + '.Service')
  SUCCESS = 0
  ALREADY = 1
  ERROR = 2

  def __init__(self, name):
    self._name = name

  def getName(self):
    """Returns the name of a Service, as a string."""
    return self._name

  @staticmethod
  def getKeys():
    """Returns a list of keys to be stored in the configuration file."""
    return []
