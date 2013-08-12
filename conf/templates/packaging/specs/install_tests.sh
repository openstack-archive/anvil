#*
    Cheetah template to be included to %install spec section
*#
# Package test environment
install -d -m 755 %{buildroot}%{tests_data_dir}
tar -cf "%{buildroot}%{tests_data_dir}/test_env.tar" \
    --exclude "./%{python_name}" \
#for i in $exclude_from_test_env
    --exclude "${i}" \
#end for
    --exclude-vcs .
find "./%{python_name}" -type d -name tests | while read testdir; do
    tar -rf "%{buildroot}%{tests_data_dir}/test_env.tar" \
#for i in $exclude_from_test_env
        --exclude "${i}" \
#end for
        "\$testdir"
done
if [ -r "./%{python_name}/test.py" ]; then
    tar -rf "%{buildroot}%{tests_data_dir}/test_env.tar" \
        ./%{python_name}/test.py
fi
gzip -9 "%{buildroot}%{tests_data_dir}/test_env.tar"


# Script that prepares test environment:
#raw
cat > %{buildroot}%{_bindir}/%{python_name}-make-test-env <<"EOF"
#!/bin/bash

set -e

if [ -z "$1" ] || [ "$1" == "--help" ] ; then
    echo "Usage: $0 [dir]"
    echo "       $0 --tmpdir"
fi

if [ "$1" == "--tmpdir" ]; then
    target_dir=$(mktemp -dt "${0##*/}.XXXXXXXX")
    echo "Created temporary directory: $target_dir"
else
    target_dir="$1"
fi

cd "$target_dir"
tar -xzf "%{tests_data_dir}/test_env.tar.gz"
cp -a %{python_sitelib}/%{python_name} .
ln -s /usr/bin ./bin

EOF
chmod 0755 %{buildroot}%{_bindir}/%{python_name}-make-test-env
#end raw
