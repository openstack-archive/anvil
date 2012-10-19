#!/bin/bash

set -u

NOSEARGS=
JUST_PEP8=0

function usage {
  echo "Usage: $0 [OPTION]..."
  echo "Run anvils test suite."
  echo ""
  echo "  -p, --pep8               Just run pep8"
  echo "  -h, --help               Print this usage message"
  echo ""
  exit
}

function process_option {
  case "$1" in
    -h|--help) usage;;
    -p|--pep8) let JUST_PEP8=1;;
    -c|--coverage) NOSEARGS="$NOSEARGS --with-coverage --cover-package=anvil";;
    *) NOSEARGS="$NOSEARGS $1"
  esac
}


function find_code {
  files=`find anvil -type f | grep "py\$"`
  echo $files
}

function run_pep8 {
  echo "Running pep8 ..."
  files=$(find_code)
  ignores="E202,E501"
  output_filename="pep8.log"
  opts="--ignore=$ignores --repeat"
  pep8 ${opts} ${files} 2>&1 > $output_filename
  if [ "$?" -ne "0" ]; then
    echo "Some badness was found!"
  fi
  echo "Check '$output_filename' for a full report."
}

function run_pylint {
  echo "Running pylint ..."
  opts="--rcfile=pylintrc --output-format=parseable"
  files=$(find_code)
  output_filename="pylint.log"
  pylint ${opts} ${files} 2>&1 > $output_filename
  if [ "$?" -eq "1" ]; then
    # pylint --long-help
    # * 0 if everything went fine
    # * 1 if a fatal message was issued
    # * 2 if an error message was issued
    # * 4 if a warning message was issued
    # * 8 if a refactor message was issued
    # * 16 if a convention message was issued
    # * 32 on usage error
    echo "A fatal pylint error occurred!"
  else
    if [ "$?" -eq "0" ]; then
      echo "Your code is perfect you code master!"
    else
      echo "You are not yet a code master."
      grep -i "Your code" $output_filename
    fi
  fi
  echo "Check '$output_filename' for a full report."
}

function run_tests {
  echo "Running tests ..."
  # Cleanup *.pyc
  find . -type f -name "*.pyc" -delete
  $NOSETESTS
}

function validate_yaml {
    echo "Validating YAML files..."
    for f in `find conf/ -name *.yaml -type f`; do
        echo "Checking yaml file: $f"
        python tools/validate-yaml.py $f
        if [ "$?" -ne "0" ]; then
          echo "File: $f has some badness in it!"
        fi
    done
}

for arg in "$@"; do
  process_option $arg
done

export NOSETESTS="nosetests $NOSEARGS"

if [ $JUST_PEP8 -eq 1 ]; then
    run_pep8
    exit 0
fi

run_tests
run_pep8
run_pylint
validate_yaml
