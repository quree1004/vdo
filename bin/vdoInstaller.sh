#!/bin/sh

#
# Copyright (c) 2013 Permabit Technology Corporation.
# @LICENSE@
# $Id: //eng/vdo-releases/nitrogen/src/c++/vdo/bin/vdoInstaller.sh.in#1 $
#

# VDO installer tool
# usage: vdoInstaller.sh [<option>...] install|uninstall|update|status
#
# Commands:
#
# install       Compiles, installs and loads the vdo device mapper module and
#               arranges for it to be loaded at system startup. This command
#               only needs to be run once for a given system -- if the vdo
#               kernel module needs to be installed for a new kernel, use
#               the update command.
#
# uninstall     Deletes the vdo kernel module (if installed) for all kernel
#               versions and removes it from the system startup list.
#               Does nothing if the module is not installed.
#
# update        If a new kernel has been installed, then a manual
#               update may be required. This action builds and installs the
#               vdo kernel module for the new kernel.
#
# status        Displays the current installation status of the vdo kernel
#               module. This command has no options, and does need to be run
#               with root privileges.
#
# Options:
#
# --moduleName          The name to be given to the module when it is installed.
# --moduleSourceDir     The directory from which the install command copies
#                       the vdo kernel module package. Defaults to the
#                       "drivers" directory.
# --kver                Sets the kernel version to build and install against.
#                       Defaults to the running kernel.
# --noRun               Displays commands instead of running them.
# --verbose             Displays commands before running them.

# Fixup path for non-root users so we can find programs such as dkms.
PATH=$PATH:/sbin:/usr/sbin:/usr/local/sbin
export PATH

# Command line options
MODULE_SOURCE_DIR=$(dirname $0)/../drivers
NORUN=0
VERBOSE=0

# Internal variables
KVER=$(uname -r)
DEFAULT_MODULE_NAME=kvdo
MODULE_NAME=$DEFAULT_MODULE_NAME
MODULE_VER="1.4.2"
DRIVER_PACKAGE=$MODULE_NAME-$MODULE_VER.tgz
MYNAME=$(basename "$0")

COMMAND=""

usage() {
  echo "usage: $MYNAME [options] install|uninstall|update|status"
  echo "options:"
  echo "       [--moduleName=NAME]"
  echo "       [--moduleSourceDir=PATH]"
  echo "       [--kver=VERSION]"
  echo "       [--noRun]"
  echo "       [--verbose]"
}

# Parse command line arguments
TEMP=`getopt -o h --long help                \
                  --long moduleName:         \
                  --long moduleSourceDir:    \
                  --long kver:               \
                  --long noRun::             \
                  --long verbose::           \
  -n $MYNAME -- "$@"`

if [ $? -ne 0 ] ; then echo "$(usage)" >&2; exit 1 ; fi

eval set -- "$TEMP"

while true
do
  case "$1" in
    -h|--help)
      COMMAND=usage; shift
      ;;
    --moduleName)
      MODULE_NAME="$2"
      shift 2
      ;;
    --moduleSourceDir)
      MODULE_SOURCE_DIR="$2"; shift 2
      ;;
    --kver)
      KVER="$2"; shift 2
      ;;
    --noRun)
      case "$2" in
	"") NORUN=1; VERBOSE=1; shift 2 ;;
	*) NORUN="$2"; VERBOSE="$2"; shift 2 ;;
      esac
      ;;
    --verbose)
      case "$2" in
	"") VERBOSE=1; shift 2 ;;
	*) VERBOSE="$2"; shift 2 ;;
      esac
      ;;
    --)
      shift
      break
      ;;
    *)
      echo "Internal error $1" >&2
      exit 1
      ;;
  esac
done

if [ -z "$COMMAND" ]; then
  if [ $# -ne 1 ]; then
    echo ERROR: Must specify exactly one command >&2
    echo "$(usage)" >&2
    exit 1
  fi

  case "$1" in
    install)
      COMMAND=installModule
      ;;
    uninstall)
      COMMAND=uninstallModule
      ;;
    update)
      COMMAND=updateModule
      ;;
    status)
      COMMAND=status
      ;;
    *)
      echo ERROR: Unknown command "$1" >&2
      echo "$(usage)" >&2
      exit 1
      ;;
  esac
fi

_rel2abs() {
  local dir
  dir=$(dirname "$1")

  if [ ! -d "$dir" ]; then
    echo "ERROR: can't resolve '$dir': does not exist" >&2
    exit 1
  fi
  echo $(cd "$dir"; pwd)/$(basename "$1")
}

_doCommand() {
  if [ "$VERBOSE" = "1" ] ; then
    echo "  $1"
  fi

  if [ "$NORUN" != "1" ] ; then
    eval $1
    if [ $? -ne 0 ] ; then
      echo ERROR: running command $1 >&2
      exit 1
    fi
  fi
}

_rootCheck() {
  if [ $(id -u) -ne 0 ] ; then
    echo ERROR: You must be root to install or uninstall modules >&2
    exit 1
  fi
}

_systemCheck() {
  if [ -e /etc/SuSE-release ] ; then
    if ! grep -q -P '^\s*allow_unsupported_modules\s+1' \
        /etc/modprobe.d/unsupported-modules; then
      echo "ERROR: $MODULE_NAME is an unsupported module and this system is not" >&2
      echo "       configured to allow them. See " >&2
      echo "       http://www.novell.com/support/kb/doc.php?id=7002793" >&2
      echo "       for more details." >&2
      exit 1
    fi
  fi
}

_buildAndInstall() {
  echo Building and installing $MODULE_NAME for Linux $KVER...
  _doCommand "dkms build -m $MODULE_NAME -v $MODULE_VER -k $KVER"
  _doCommand "dkms install -m $MODULE_NAME -v $MODULE_VER -k $KVER"
  if [ "$KVER" = $(uname -r) ]; then
    echo Loading $MODULE_NAME...
    _doCommand "modprobe $MODULE_NAME"
  else
    echo Skipping loading of $MODULE_NAME: not building for running kernel
  fi
}

_renameModule() {
    MODULE_BUILD_DIR="/usr/src/$MODULE_NAME-$MODULE_VER"
    REPLACE="sed -e 's/$DEFAULT_MODULE_NAME/$MODULE_NAME/g'"
    RENAME=`cat <<EOF
mv /usr/src/$DEFAULT_MODULE_NAME-$MODULE_VER $MODULE_BUILD_DIR &&
mv $MODULE_BUILD_DIR/Makefile $MODULE_BUILD_DIR/Makefile.bak &&
$REPLACE $MODULE_BUILD_DIR/Makefile.bak > $MODULE_BUILD_DIR/Makefile &&
mv $MODULE_BUILD_DIR/dkms.conf $MODULE_BUILD_DIR/dkms.conf.bak &&
$REPLACE $MODULE_BUILD_DIR/dkms.conf.bak > $MODULE_BUILD_DIR/dkms.conf
EOF
`
    _doCommand "$RENAME"
}

installModule() {
  _rootCheck
  _systemCheck

  local SOURCE
  SOURCE=$(_rel2abs "$MODULE_SOURCE_DIR/$DRIVER_PACKAGE")
  if [ ! -f "$SOURCE" ] ; then
    echo ERROR: can\'t unpack driver package: File $SOURCE not found >&2
    exit 1
  fi

  echo Unpacking $MODULE_NAME driver package...
  _doCommand "(cd /usr/src && tar zxf '$SOURCE')"

  if [ "$MODULE_NAME" != "$DEFAULT_MODULE_NAME" ] ; then
      _renameModule
  fi

  echo Adding $MODULE_NAME to the DKMS dB...
  _doCommand "dkms add -m $MODULE_NAME -v $MODULE_VER"
  _buildAndInstall
}

uninstallModule() {
  _rootCheck
  echo Uninstalling module $MODULE_NAME...

  if lsmod | grep -q "^$MODULE_NAME" ; then
    _doCommand "modprobe -r $MODULE_NAME"
  fi

  if [ -n "$(dkms status -m $MODULE_NAME -v $MODULE_VER)" ] ; then
    _doCommand "dkms remove -m $MODULE_NAME -v $MODULE_VER --all"
  fi
  _doCommand "rm -rf /usr/src/$MODULE_NAME-$MODULE_VER"
}

updateModule() {
  _rootCheck
  _buildAndInstall
}

status() {
  local dkmsStatus
  local modulesDir
  modulesDir=/lib/modules/$KVER
  dkmsStatus=$(dkms status -m $MODULE_NAME -v $MODULE_VER -k $KVER | cut -f2 -d:)
  if [ -z "$dkmsStatus" ] ; then
    dkmsStatus=" N/A"
  fi

  echo "Kernel module:"
  echo "  Name: ${MODULE_NAME}.ko"
  echo "  Version: $MODULE_VER"
  echo "  Kernel: $KVER"
  echo "  State:$dkmsStatus"
  echo -n "  In module dependency file:"
  if grep -q "${MODULE_NAME}.ko" $modulesDir/modules.dep; then
    echo " y"; else echo " n"; fi
  echo -n "  Module loaded:"
  if [ "$KVER" = $(uname -r) ]; then
    if lsmod | grep -q "^$MODULE_NAME"; then
      echo " y"; else echo " n"; fi
  else
    echo " N/A"
  fi
}

$COMMAND
exit 0
