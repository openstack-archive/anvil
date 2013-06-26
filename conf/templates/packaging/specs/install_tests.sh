#*
    Cheetah template to be included to %install spec section
*#
#raw
# Package test environment
install -d -m 755 %{buildroot}%{tests_data_dir}
tar -cf "%{buildroot}%{tests_data_dir}/test_env.tar" \
    --exclude-vcs  --exclude ./%{python_name} --exclude './build*' --exclude './bin' .
if [ -d "./%{python_name}/tests" ]; then
    tar -rf "%{buildroot}%{tests_data_dir}/test_env.tar" \
        ./%{python_name}/tests
fi
if [ -r "./%{python_name}/test.py" ]; then
    tar -rf "%{buildroot}%{tests_data_dir}/test_env.tar" \
        ./%{python_name}/test.py
fi
gzip -9 "%{buildroot}%{tests_data_dir}/test_env.tar"


# Make simple test runner
cat > %{buildroot}%{_bindir}/%{python_name}-run-unit-tests <<"EOF"
#!/bin/bash

set -e

# These settings are overridable from command line
export NOSE_VERBOSE=2
export NOSE_WITH_OPENSTACK=1
export NOSE_OPENSTACK_COLOR=1
export NOSE_OPENSTACK_RED=0.05
export NOSE_OPENSTACK_YELLOW=0.025
export NOSE_OPENSTACK_SHOW_ELAPSED=1

# Create temporary directory, remove it on exit:
tmpdir=
cleanup_tmpdir()
{
    [ -z "$tmpdir" ] || rm -rf -- "$tmpdir"
    exit "$@"
}
tmpdir=$(mktemp -dt "${0##*/}.XXXXXXXX")
trap 'cleanup_tmpdir $?' EXIT
trap 'clenaup_tmpdir 143' HUP INT QUIT PIPE TERM

cd "$tmpdir"
tar -xzf "%{tests_data_dir}/test_env.tar.gz"
cp -a %{python_sitelib}/%{python_name} .
ln -s /usr/bin ./bin

exec nosetests \
#end raw
#for i in $exclude_tests
    --exclude "${i}" \
#end for
#raw
    "$@"

EOF
chmod 0755 %{buildroot}%{_bindir}/%{python_name}-run-unit-tests
#end raw
