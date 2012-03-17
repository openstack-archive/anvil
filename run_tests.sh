#!/bin/bash

set -eu

function usage {
  echo "Usage: $0 [OPTION]..."
  echo "Run Devstacks's test suite(s)"
  echo ""
  echo "  -O, --only test_suite    Only run the specified test suite. Valid values are:"
  echo "                               Note: by default, run_tests will run all suites."
  echo "  -V, --virtual-env        Always use virtualenv.  Install automatically if not present."
  echo "  -N, --no-virtual-env     Don't use virtualenv.  Run tests in local environment."
  echo "  -x, --stop               Stop running tests after the first error or failure."
  echo "  -f, --force              Force a clean re-build of the virtual environment. Useful when dependencies have been added."
  echo "                             Note: you might need to 'sudo' this since it pip installs into the virtual environment."  
  echo "  -P, --skip-pep8          Just run tests; skip pep8 check."
  echo "  -p, --pep8               Just run pep8."
  echo "  -l, --pylint             Just run pylint."
  echo "  -y, --yaml               Just validate YAML."
  echo "  -c, --with-coverage      Generate coverage report."
  echo "  -h, --help               Print this usage message."
  echo "  --hide-elapsed           Don't print the elapsed time for each test along with slow test list."
  echo "  --verbose                Print additional logging."
  echo ""
  echo "Note: with no options specified, the script will try to run the tests in a virtual environment,"
  echo "      If no virtualenv is found, the script will ask if you would like to create one.  If you "
  echo "      prefer to run tests NOT in a virtual environment, simply pass the -N option."
  echo ""
  echo "Note: with no options specified, the script will run the pep8 check after completing the tests."
  echo "      If you prefer not to run pep8, simply pass the -P option."
  exit
}

only_run_flag=0
only_run=""
function process_option {
  if [ $only_run_flag -eq 1 ]; then
    only_run_flag=0
    only_run=$1
    return
  else
    case "$1" in
      -h|--help) usage;;
      -V|--virtual-env) always_venv=1; never_venv=0;;
      -N|--no-virtual-env) always_venv=0; never_venv=1;;
      -O|--only) only_run_flag=1;;
      -f|--force) force=1;;
      -P|--skip-pep8) skip_pep8=1;;
      -p|--pep8) just_pep8=1;;
      -l|--pylint) just_pylint=1;;
      -y|--yaml) just_yaml=1;;
      -c|--with-coverage) coverage=1;;
      -*) addlopts="$addlopts $1";;
      *) addlargs="$addlargs $1"
    esac
  fi
}

venv=.venv
with_venv=tools/with_venv.sh
always_venv=0
never_venv=0
force=0
addlargs=
addlopts=
wrapper=""
just_pep8=0
skip_pep8=0
just_pylint=0
just_yaml=0
coverage=0
pylintrc_fn="pylintrc"

for arg in "$@"; do
  process_option $arg
done

# If enabled, tell nose/unittest to collect coverage data
if [ $coverage -eq 1 ]; then
    addlopts="$addlopts --with-coverage --cover-package=devstack"
fi

if [ "x$only_run" = "x" ]; then
    RUNTESTS="python run_tests.py$addlopts$addlargs"
else
    RUNTESTS="python run_tests.py$addlopts$addlargs -O $only_run"
fi

if [ $never_venv -eq 0 ]
then
  # Remove the virtual environment if --force used
  if [ $force -eq 1 ]; then
    echo "Cleaning virtualenv..."
    rm -rf ${venv}
  fi
  if [ -e ${venv} ]; then
    wrapper="${with_venv}"
  else
    if [ $always_venv -eq 1 ]; then
      # Automatically install the virtualenv
      python tools/install_venv.py
      wrapper="${with_venv}"
    else
      echo -e "No virtual environment found...create one? (Y/n) \c"
      read use_ve
      if [ "x$use_ve" = "xY" -o "x$use_ve" = "x" -o "x$use_ve" = "xy" ]; then
        # Install the virtualenv and run the test suite in it
        python tools/install_venv.py
        wrapper=${with_venv}
      fi
    fi
  fi
fi

function run_tests {
  OFN="run_tests.log"
  # Just run the test suites in current environment
  ${wrapper} $RUNTESTS 2>$OFN | tee $OFN
  # If we get some short import error right away, print the error log directly
  RESULT=$?
  echo "Check '$OFN' for a full error report."
  if [ "$RESULT" -ne "0" ];
  then
    ERRSIZE=`wc -l $OFN | awk '{print \$1}'`
    if [ "$ERRSIZE" -lt "40" ];
    then
        cat $OFN
    fi
  fi
  return $RESULT
}

function run_pep8 {
  echo "Running pep8 ..."
  SRC_FILES=`find devstack -type f | grep "py\$"`
  SRC_FILES+=" stack run_tests.py"
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
  PYLINT_OPTIONS="--rcfile=$pylintrc_fn --output-format=parseable"
  PYLINT_INCLUDE=`find devstack -type f | grep "py\$"`
  PYLINT_INCLUDE+=" stack run_tests.py"
  TEE_FN="pylint.log"
  echo "Pylint messages count: "
  pylint ${PYLINT_OPTIONS} ${PYLINT_INCLUDE} 2>&1 | tee $TEE_FN | grep 'devstack/' | wc -l
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
        tools/validate_yaml.py $f
    done
}


# Delete old coverage data from previous runs
if [ $coverage -eq 1 ]; then
    ${wrapper} coverage erase
fi

if [ $just_pep8 -eq 1 ]; then
    run_pep8
    exit
fi

if [ $just_pylint -eq 1 ]; then
    run_pylint
    exit
fi

if [ $just_yaml -eq 1 ]; then
    validate_yaml
    exit
fi


echo "Running tests..."
run_tests

if [ $skip_pep8 -eq 0 ]; then
    # Run the pep8 check
    run_pep8
fi

# Since we run multiple test suites, we need to execute 'coverage combine'
if [ $coverage -eq 1 ]; then
    echo "Generating coverage report in covhtml/"
    ${wrapper} coverage combine
    ${wrapper} coverage html -d covhtml -i
    ${wrapper} coverage report --omit='/usr*,devstack/test*,.,setup.py,*egg*,/Library*,*.xml,*.tpl'
fi

