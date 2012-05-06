#!/bin/bash

set -eu

function run_pep8 {
  echo "Running pep8 ..."
  SRC_FILES=`find anvil -type f | grep "py\$"`
  SRC_FILES+=" smithy"
  PEP_IGNORES="E202,E501"
  TEE_FN="pep8.log"
  PEP8_OPTS="--ignore=$PEP_IGNORES --repeat"
  pep8 ${PEP8_OPTS} ${SRC_FILES} 2>&1 | tee $TEE_FN
  if [ "$?" -ne "0" ]; then
      echo "Sorry, cannot run pep8 ..."
      exit 1
  else
      echo "Successfully ran pep8 ..."
      echo "Check '$TEE_FN' for a full report."
  fi
}

function run_pylint {
  echo "Running pylint ..."
  PYLINT_OPTIONS="--rcfile=pylintrc --output-format=parseable"
  PYLINT_INCLUDE=`find anvil -type f | grep "py\$"`
  PYLINT_INCLUDE+=" smithy"
  TEE_FN="pylint.log"
  echo "Pylint messages count: "
  pylint ${PYLINT_OPTIONS} ${PYLINT_INCLUDE} 2>&1 | tee $TEE_FN | grep 'anvil/' | wc -l
  if [ "$?" -ne "0" ]; then
      echo "Sorry, cannot run pylint ..."
      exit 1
  else
      echo "Successfully ran pylint ..."
      echo "Check '$TEE_FN' for a full report."
  fi
}

function validate_yaml {
    echo "Validating YAML files..."
    for f in `find conf/ -name *.yaml -type f`; do
        echo "Checking yaml file: $f"
        tools/validate-yaml.py $f
    done
}

run_pep8
run_pylint
validate_yaml

