#!/bin/bash

set -eu


function usage {
  echo "Usage: $0 [OPTION]..."
  echo "  --no-pep8               Don't run pep8"
  echo "  --no-pylint             Don't run pylint"
  echo "  -h, --help               Print this usage message"
  exit
}


function process_option {
  case "$1" in
    -h|--help) usage;;
    --no-pep8) pep8=0;;
    --no-pylint) pylint=0;;
    -*);;
    *);;
  esac
}


pylint=1
pep8=1
wrapper="exec"
pylintrc_fn="pylintrc"


for arg in "$@"; do
  process_option $arg
done


function run_pep8 {
  echo "Running pep8 ..."
  srcfiles=`find devstack -type f | grep "py\$"`
  srcfiles+=" stack"
  pep_ignores="E202,E501"
  tee_fn="pep8.log"
  pep8_opts="--ignore=$pep_ignores --repeat"
  echo "$(${wrapper} pep8 ${pep8_opts} ${srcfiles} 2>&1 | tee $tee_fn)"
  if [ "$?" -ne "0" ]; then
    echo "Sorry, cannot run pep8 ..."
    exit 1
  else
    echo "Successfully ran pep8 ..."
  fi
}


function run_pylint {
  echo "Running pylint ..."
  srcfiles=`find devstack -type f | grep "py\$"`
  srcfiles+=" stack"
  tee_fn="pylint.log"
  pylint_opts="--rcfile=$pylintrc_fn"
  echo "$(${wrapper} pylint ${pylint_opts} ${srcfiles} 2>&1 | tee $tee_fn)"
  if [ "$?" -ne "0" ]; then
   echo "Sorry, cannot run pylint ..."
   exit 1
  else
   echo "Successfully ran pylint ..."
  fi
}


if [ $pep8 -eq 1 ]; then
    run_pep8
fi

if [ $pylint -eq 1 ]; then
    run_pylint
fi

exit 0
