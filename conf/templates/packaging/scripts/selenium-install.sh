python setup.py install -O1 --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES

# remove driver parts for other architectures
%ifnarch %ix86
rm -rf %{python_sitelib}/selenium/webdriver/firefox/x86
%endif
%ifnarch x86_64
rm -rf %{python_sitelib}/selenium/webdriver/firefox/amd64
%endif

abspath_installed_files=$(readlink -f INSTALLED_FILES)
(
    cd $RPM_BUILD_ROOT
    for i in usr/*/python*/site-packages/* usr/bin/*; do
        if [ -e "$i" ]; then
            sed -i "s@/$i/@DELETE_ME@" "$abspath_installed_files"
            echo "/$i"
        fi
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

