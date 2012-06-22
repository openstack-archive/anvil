#!/usr/bin/env python
import os
import sys
import yum
import re

####
# This program reads through the RHEL distro definition and updates
# the package versions to the latest available ones.  It's set up to
# just emit the major and minor version numbers -- see
# get_package_version().
#
# I wanted to do this with PyYaml, but there's no way to losslessly
# roundtrip with PyYaml.  It drops comments and changes key orders,
# etc.  They should at least give you the option of schlepping the
# location (i.e., line, columns) with all of the tokens so you can
# manually reconstruct the file, I think.  But anyway, I took a dumber
# approach. :)
####

# cache this guy cuz he's slow to construct
yb = yum.YumBase()

def get_package_version(name):
    global yb
    pkgs = yb.pkgSack.returnNewestByNameArch(patterns=[name])
    if pkgs:
        version = pkgs[0].version
        # lets stick to just two dots...
        version = ".".join(version.split(".")[:2]) + "*"
        return version
    else:
        print >>sys.stderr, "Package " + name + " not found!"
        return "JIMMY" 

class Package(object):
    txt = ''
    name = ''

    def finish(self, output_file):
        output_file.write( self.txt.replace('JIMMY', get_package_version(self.name)))
        self.txt = ''
        self.name = ''
                
def main():
    # I wanted to use pipes, but the yum library spams stdout :(
    if len(sys.argv) < 3:
        me = os.path.basename(__file__)
        print >>sys.stderr, "usage: " + me + " <old yaml file> <new yaml file>"
        exit(1)
    input_file = file(sys.argv[1])
    output_file = file(sys.argv[2], "w")

    # some state variables used in the grotty loop below
    in_packages = False
    package = Package()
    indent = 0

    for line in input_file:
        # pass comments through
        if re.match('^\s*#.*', line):
            output_file.write(line)
            continue

        # handle in/out-dents
        match = re.match('^(\s*-?\s*)', line)
        if in_packages and indent == 0:
            indent = len(match.group(1))
        elif in_packages and len(match.group(1)) < indent:
            package.finish(output_file)
            indent = 0
            in_packages = False

        # in the packages dict, handle individual packages
        if in_packages:
            match = re.match('^(\s+-?\s*)([^:]+:)(.*)', line)
            # we only handle lines with "key: value" on the same line,
            # the rest gets passed through.
            if not match or len(match.group(1)) > indent:
                package.txt += line
                continue
            # dash on the beginning means a new package is starting
            if match.group(1).find('-') >= 0 and package.txt:
                package.finish(output_file)
            # handle the name and version keys specially
            if match.group(2) == 'name:':
                package.name = match.group(3).strip()
                package.txt += line
            elif match.group(2) == 'version:':
                package.txt += match.group(1) + match.group(2) + " JIMMY\n"
            else:
                package.txt += line

        # scan for a packages dict
        else:
            output_file.write(line)
            match = re.match('^(\s+)packages:\s*', line)
            if match:
                in_packages = True
    
if __name__ == '__main__':
    main()
