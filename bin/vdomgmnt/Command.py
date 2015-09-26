"""
  Command - runs commands and manages their results

  Copyright (c) 2012-2014 Permabit Technology Corporation.
  @LICENSE@
  $Id: //eng/vdo-releases/nitrogen/src/c++/vdo/bin/vdomgmnt/Command.py#2 $

"""
from . import Logger
import copy
import logging
import os
import string
import time


class CommandError(Exception):
  """Exception raised to indicate an error running a command."""
  def __init__(self, msg):
    super(CommandError, self).__init__()
    self._msg = msg
  def __str__(self):
    return self._msg


class Command(object):
  """Command encapsulates shell commands, runs them, and manages
  the result. Implements Callable.

  Attributes:
    exitCode (int): exit code from the last run of the command
    exitStatus (str): status summary from the last run, a la the shell
    noRun (bool): if True, don't run the command, and always succeed
    shell (bool): if True, run this command using shell -c
    stderr (str): stderr from the last run of the command
    stdout (str): stdout from the last run of the command
    verbose (int): if > 0, print commands to stdout before executing them
    _argv (int): count of items in the command line
    _cmdList (list): command and its arguments
    _cmdLine (string): the command line
    _numRun (int): the number of times this command has been run
  """
  defaultNoRun = False
  defaultVerbose = 0
  log = logging.getLogger(Logger.myname + '.Command')

  @classmethod
  def setDefaults(cls, options):
    """Sets the verbose and noRun default values from command line options.

    Arguments:
      options: The OptionParser argument object.
    """
    if options.noRun:
      cls.defaultNoRun = options.noRun
      cls.defaultVerbose = True
    if options.verbose:
      cls.defaultVerbose = options.verbose

  @classmethod
  def noRunMode(cls):
    """Returns True iff Commands default to noRun."""
    return cls.defaultNoRun

  def __init__(self, cmdList):
    self.env = None
    self.exitCode = None
    self.exitStatus = None
    self.noRun = Command.defaultNoRun
    self.shell = False
    self.sshHost = None
    self.sshOptions = []
    self.sudo = False
    self.stderr = None
    self.stdout = None
    self.verbose = Command.defaultVerbose
    self._argv = len(cmdList)
    self._cmdList = cmdList
    self._cmdLine = string.join(self._cmdList, ' ')
    self._numRun = 0

  def __str__(self):
    return self._cmdLine

  def __repr__(self):
    lst = ["Command", "["]
    lst.append(','.join('='.join([key, str(getattr(self, key))])
                        for key in self.__dict__))
    lst.append("]")
    return "".join(lst)

  def cmdName(self):
    """Returns an identifier (argv[0]) for error messages."""
    return self._cmdList[0]

  def addArg(self, arg):
    """Add an argument to this command.

    Arguments:
      arg (str): the argument to add
    """
    self._cmdList.append(arg)
    self._cmdLine = string.join(self._cmdList, ' ')
    self._argv = len(self._cmdList)

  def realCmdList(self):
    """Returns the command list decorated according to the settings
    of 'sudo' and the ssh attributes."""
    cmdList = copy.deepcopy(self._cmdList)
    if self.sudo and os.getuid() != 0:
      cmdList.insert(0, "sudo")
    if self.sshHost:
      sshList = ['ssh', self.sshHost]
      if self.sshOptions:
        sshList.extend(self.sshOptions)
      sshList.extend(cmdList)
      cmdList = sshList
    return cmdList

  def prependArg(self, arg):
    """Prepend an argument to this command.

    Arguments:
      arg (str): the argument to prepend
    """
    self._cmdList.insert(0, arg)
    self._cmdLine = string.join(self._cmdList, ' ')
    self._argv = len(self._cmdList)

  def __call__(self):
    """Runs this command.

    Exceptions:
      CommandError: command failed
    """
    from subprocess import Popen, PIPE
    success = True
    self._numRun += 1

    cmdList = self.realCmdList()
    cmdLine = string.join(cmdList, ' ')

    if self.verbose > 0:
      print('    ' + cmdLine)
    self.log.info(cmdLine)
    if self.noRun:
      return

    try:
      if self.shell:
        p = Popen(cmdLine, stdin=PIPE, stdout=PIPE, stderr=PIPE,
                  close_fds=True, env=self.env, shell=True)
      else:
        p = Popen(cmdList, stdin=PIPE, stdout=PIPE, stderr=PIPE,
                  close_fds=True, env=self.env)
    except OSError as (err, strerror):
      self._setFromException(err, strerror)
      raise CommandError(self.exitStatus)

    stdoutdata, stderrdata = p.communicate()
    self.stdout = "".join(stdoutdata)
    self.stderr = "".join(stderrdata)
    self.exitCode = p.returncode
    self._setExitStatus()
    if self.exitCode != 0:
      success = False
    self.log.debug('exit status: ' + self.exitStatus)
    self.log.debug('stdout: ' + self.stdout.rstrip())
    self.log.debug('stderr: ' + self.stderr.rstrip())
    if not success:
      errtxt = self.stderr.split(os.linesep)[0]
      if errtxt:
        raise CommandError(errtxt)
      else:
        raise CommandError(self.exitStatus)

  def _setExitStatus(self):
    """Sets exitStatus from the current value of exitCode."""
    if self.exitCode < 0:
      self.exitStatus = _(
          "{cmdname}: command failed, signal {signal}").format(
          cmdname=self.cmdName(), signal=-self.exitCode)
    elif self.exitCode == 0:
      self.exitStatus = _("{cmdname}: command succeded").format(
        cmdname=self.cmdName())
    else:
      self.exitStatus = _(
        "{cmdname}: command failed, exit status {status}").format(
        cmdname=self.cmdName(), status=self.exitCode)

  def _setFromException(self, err, strerror):
    """Sets result values from exception information.

    Arguments:
      err (int): the errno from the exception
      strerror (str): the printable error message
    """
    self.stdout = ""
    self.stderr = self.cmdName() + ": " + strerror
    self.exitCode = (err >> 8) & 0xff
    self.exitStatus = _(
      "{cmdname}: command failed: {strerror}").format(
      cmdname=self.cmdName(), strerror=strerror)
    self.log.debug('exit status: ' + self.exitStatus)

  def mock(self, exitCode=0, stdout='', stderr=''):
    """Artificially sets the result values of this object. Used to make
    noRun do something other than succeed with no output.

    Arguments:
      exitCode (int): the fake process exit code
      stdout (str): the fake standard output
      stderr (str): the fake standard error
    """
    self.exitCode = exitCode
    self._setExitStatus()
    self.stdout = stdout
    self.stderr = stderr

  def setenv(self, var, value):
    """Adds or modifies environment variables used when running this command.

    Arguments:
      var (str): the environment variable to add
      value (str): the value of the environment variable
    """
    if not self.env:
      self.env = copy.deepcopy(os.environ)
    self.env[var] = value

  def runOutput(self):
    """Convenience function: run this command and return its standard
    output as a string. Returns an empty string in case of failure.
    This is like `command ...` in the shell.
    """
    try:
      self()
      return self.stdout
    except CommandError:
      return ''

  def waitFor(self, retries=20):
    """Runs this command repeatedly until is succeeds or times out.
    The command is run at one-second intervals.

    Arguments:
      retries: number of retries
    """
    cmdList = self.realCmdList()
    cmdLine = string.join(cmdList, ' ')
    self.log.debug("Waiting for '{0}'".format(cmdLine))
    if self.noRun:
      return

    for count in range(retries):
      self.log.debug("  ... {0}/{1}".format(str(count), str(retries)))
      try:
        self()
        return
      except CommandError:
        time.sleep(1)
    raise CommandError(_("{cmdname}: timed out after {sec} seconds").format(
        cmdname=self.cmdName(), sec=str(retries)))

  def noThrowCall(self):
    """Runs this command, swallowing exceptions. For applications like
    destructors and cleanup."""
    try:
      self()
    except CommandError as ex:
      self.log.debug("{cmdname}: swallowed exception {ex}".format(
        cmdname=self.cmdName(), ex=ex))
