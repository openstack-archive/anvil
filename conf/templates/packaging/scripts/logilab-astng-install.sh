python setup.py install --single-version-externally-managed -O1 --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES
abspath_installed_files=$(readlink -f INSTALLED_FILES)
(
    cd $RPM_BUILD_ROOT
    for i in usr/*/python*/site-packages/* usr/bin/*; do
        if [ -e "$i" ]; then
            sed -i "s@/$i/@DELETE_ME@" "$abspath_installed_files"
        fi
    done
    for i in usr/*/python*/site-packages/logilab/astng usr/*/python*/site-packages/logilab_astng*; do
        echo "/$i"
    done
    if [ -d usr/man ]; then
        rm -rf usr/share/man
        mkdir -p usr/share
        mv usr/man usr/share/
        sed -i "s@/usr/man/@DELETE_ME@" "$abspath_installed_files"
        for i in usr/share/man/*; do
            echo "/$i/*"
        done
    fi
) >> GATHERED_FILES
{ sed '/^DELETE_ME/d' INSTALLED_FILES; cat GATHERED_FILES; } | sort -u > INSTALLED_FILES.tmp
mv -f INSTALLED_FILES{.tmp,}

# Provided by the python-logilab-common package
rm -f %{buildroot}%{python_sitelib}/logilab/__init__.*
