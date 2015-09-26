"""
  InitScriptService - manages the /etc/init.d script

  Copyright (c) 2012-2013 Permabit Technology Corporation.
  @LICENSE@
  $Id: //eng/vdo-releases/nitrogen/src/c++/vdo/bin/vdomgmnt/InitScriptService.py#2 $

"""
from . import Brand, Command, CommandError, Logger, Service
import os


class InitScriptService(Service):
  """InitScriptService manages the /etc/init.d script on the local node."""
  log = Logger.getLogger(Logger.myname + '.Service.InitScriptService')

  def __init__(self, **kw):
    Service.__init__(self, Brand.map('kvdo'))
    self._basePath = '/bin:/sbin:/usr/bin:/usr/sbin'
    self._confFile = kw.get('confFile')
    self._customFile = kw.get('customFile')
    self._logLevel = kw.get('logLevel')
    self._scriptName = '/etc/init.d/' + self._name
    self._shortDescription = _("Permabit VDO volume services")

  def __str__(self):
    return "InitScriptService(\"{0}\")".format(self.getName())

  def __repr__(self):
    lst = [self.__str__(), "["]
    lst.append(','.join('='.join([key, str(getattr(self, key))])
                        for key in self.__dict__))
    lst.append("]")
    return "".join(lst)

  def getInitScript(self, addPath):
    """Returns the init script contents as a string."""
    path = self._basePath
    if addPath != '':
      path += os.pathsep + addPath
    scriptArgList = ["--syslog"]
    if self._confFile:
      scriptArgList.extend(["--confFile", self._confFile])
    if self._customFile:
      scriptArgList.extend(["--customFile", self._customFile])
    if self._logLevel:
      scriptArgList.extend(["--vdoLogLevel", self._logLevel])
    scriptArgs = ' '.join(scriptArgList)
    text = """### BEGIN INIT INFO
# Provides:          {name}
# Required-Start:    $network $local_fs $remote_fs
# Required-Stop:     $network $local_fs $remote_fs
# Should-Start:
# Should-Stop:
# Default-Start:     2 3 5
# Default-Stop:      0 1 6
# Short-Description: {desc}
# Description:       VDO volume services provides deduplicating
#	block devices using the Albireo deduplication
#	service.
### END INIT INFO

PATH={path}
DESC="{desc}"
VDO_MANAGER_SCRIPT={script}
VDO_MANAGER_CMD="{script} {scriptArgs}"

. /lib/lsb/init-functions

# Exit if required binaries are missing
[ -x $VDO_MANAGER_SCRIPT ] || {{ echo "$VDO_MANAGER_SCRIPT not installed";
                        exit 5; }}

# Use log_daemon_msg if it is available, otherwise just use echo
type log_daemon_msg 2>/dev/null | grep -q function || {{
    alias log_daemon_msg=/bin/echo
}}

case $1 in
    start)
        log_daemon_msg "Starting $DESC"
        LANG=en $VDO_MANAGER_CMD --all start
        ;;
    stop)
        log_daemon_msg "Stopping $DESC"
        LANG=en $VDO_MANAGER_CMD --force --all stop
        ;;
    restart|force-reload)
        $0 stop
        sleep 1
        $0 start
        ;;
    status)
        echo -n "{name} volumes: "
        LANG=en $VDO_MANAGER_CMD list
        ;;
    *)
        echo 'Usage: {name} {{start|stop|status|restart}}' >&2
        exit 3
        ;;
esac

exit 0
""".format(name=self._name, script=Logger.mypath, scriptArgs=scriptArgs,
           path=path, desc=self._shortDescription)
    return text

  def create(self, addPath):
    """Creates and installs the init script."""
    import tempfile
    if self.have():
      self.log.info(_("Init script {name} already present").format(
          name = self._name))
      return self.SUCCESS

    text = self.getInitScript(addPath)
    tmpf, tmpnam = tempfile.mkstemp()
    try:
      os.write(tmpf, text)
      os.close(tmpf)
    except OSError:
      self.log.error(_("Could not create temporary file"))
      return self.ERROR

    try:
      mvCmd = Command(['mv', tmpnam, self._scriptName])
      mvCmd()
    except CommandError:
      self.log.error(_("Could not create init script"))
      os.unlink(tmpnam)
      return self.ERROR

    try:
      self.insserv()
    except CommandError:
      self.log.error(_("Could not install init script"))
      return self.ERROR
    # Make sure init script configuration is on persistent storage
    os.system("sync")
    return self.SUCCESS

  def insserv(self):
    """Attempts to add the init script with insserv and failing that,
    attempts to add the init script with chkconfig.

    Exceptions:
      CommandError: neither command can be run successfully
    """
    chmodCmd = Command(['chmod', '755', self._scriptName])
    chmodCmd()
    insservCmd = Command(['insserv', '-d', self._scriptName])
    try:
      insservCmd()
      return
    except CommandError:
      pass

    chkConfigCmd = Command(['chkconfig', '--add', self._scriptName])
    chkConfigCmd()

  def remove(self):
    """Removes the init script."""
    if self.have():
      insservCmd = Command(['insserv', '-r', self._scriptName])
      rmCmd = Command(['rm', '-f', self._scriptName])
      try:
        insservCmd()
        rmCmd.noThrowCall()
        return self.SUCCESS
      except CommandError:
        pass

      chkconfigCmd = Command(['chkconfig', '--del', self._scriptName])
      try:
        chkconfigCmd()
        rmCmd.noThrowCall()
      except CommandError:
        self.log.warn(_("Cannot remove init script {0}").format(
            self._scriptName))
        return self.ERROR
    return self.SUCCESS

  def have(self):
    """Returns true if the init script exists."""
    return os.path.isfile(self._scriptName)
