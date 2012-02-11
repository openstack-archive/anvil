import json
import os
import sys
import re
import subprocess

#useful for running like the following
#find conf/ | grep ".json\$" | xargs python utils/check-avail.py "rhel-6"
#on a rhel6 system

BASE_CMD = ['yum', 'provides']
VER_LEN = 10
MAX_SUB_SEGMENTS = 2

def clean_file(name):
    with open(name, "r") as f:
        contents = f.read()
        lines = contents.splitlines()
        cleaned_up = list()
        for line in lines:
            if line.lstrip().startswith('#'):
                continue
            else:
                cleaned_up.append(line)
        cleaned_lines = os.linesep.join(cleaned_up)
        data = json.loads(cleaned_lines)
        return data


def versionize(ver):
    real_digits = list()
    for i in range(VER_LEN):
        if i < len(ver):
            digit = ver[i].strip().strip("*")
            if not len(digit):
                real_digits.append("0" * MAX_SUB_SEGMENTS)
            else:
                for j in range(MAX_SUB_SEGMENTS):
                    if j < len(digit):
                        real_digits.append(digit[j])
                    else:
                        real_digits.append("0")
        else:
            real_digits.append("0" * MAX_SUB_SEGMENTS)
    ver_str = "".join(real_digits)
    return int(ver_str)


def pick_version(old_ver, new_ver):
    if new_ver is None:
        return old_ver
    if old_ver is None:
        return new_ver
    try:
        old_v = versionize(old_ver.strip("*").split("."))
        new_v = versionize(new_ver.strip("*").split("."))
        if old_v < new_v:
            return new_ver
        else:
            return old_ver
    except ValueError:
        return old_ver

def version_check(stdout, name, version):
    lines = stdout.splitlines()
    founds = list()
    #this seems to happen
    #where we have a pkg named 111:blah.4.33
    #now sure what those are
    cleaner = re.compile(r"^([\d]*):(.*)$", re.IGNORECASE)
    #just check that it is the right line
    for line in lines:
        line = line.strip()
        mtch = cleaner.match(line)
        if mtch:
            line = mtch.group(2).strip()
        if line.startswith(name):
            founds.append(line)
    #now clean off the garbage
    possibles = list()
    for found in founds:
        pieces = found.split(":", 1)
        if len(pieces) >= 1:
            poss = pieces[0].strip()
            if poss:
                possibles.append(poss)
    #now isolate the versions
    myver = versionize(version.strip("*").split("."))
    versions_found = dict()
    prog_ver = re.compile(r"^([\d\.]*)(.*el6.*)$", re.IGNORECASE)
    for p in possibles:
        if p.startswith(name):
            verinfo = p[len(name):len(p)]
            verinfo = verinfo.strip("-")
            vermatcher = prog_ver.match(verinfo)
            if vermatcher:
                v = vermatcher.group(1)
                aver = versionize(v.strip("*").split("."))
                if aver is not None:
                    versions_found[p] = aver
    #now see if good enough
    if not versions_found:
        #nothing found at all
        return (False, None, None)
    else:
        #see if completly satisfied
        for (name, version) in versions_found.items():
            if version >= myver:
                return (True, name, version)
        #find the closest match
        min_dist = None
        closest_name = None
        closest_version = None
        for (name, version) in versions_found.items():
            dist = abs(myver - version)
            if min_dist is None or dist < min_dist:
                closest_name = name
                min_dist = dist
                closest_version = version
        return (False, closest_name, closest_version)

def find_closest(pkgname, version):
    try:
        stdin_fh = subprocess.PIPE
        stdout_fh = subprocess.PIPE
        stderr_fh = subprocess.PIPE
        cmd = BASE_CMD + [pkgname]
        obj = subprocess.Popen(cmd,
                       stdin=stdin_fh,
                       stdout=stdout_fh,
                       stderr=stderr_fh,
                       close_fds=True,
                       cwd=None,
                       shell=False,
                       env=None)
        result = obj.communicate()
        rc = obj.returncode
        if rc == 0:
            (stdout, stderr) = result
            return version_check(stdout, pkgname, version)
        else:
            #guess not
            return (False, None, None)
    except OSError:
        #guess not
        return (False, None, None)

if __name__ == "__main__":
    ME = os.path.basename(sys.argv[0])
    if len(sys.argv) == 1:
        print("%s distro filename filename filename..." % (ME))
        sys.exit(0)
    distro = sys.argv[1]
    fns = sys.argv[2:len(sys.argv)]
    pkgs = dict()
    pips = dict()
    for fn in fns:
        data = clean_file(fn)
        is_pip = False
        if fn.find("pip") != -1:
            #TODO this isn't that great
            is_pip = True
        if distro in data:
            for (name, info) in data[distro].items():
                if is_pip:
                    if name in pips:
                        my_ver = info.get("version")
                        old_ver = pips[name]
                        pips[name] = pick_version(old_ver, my_ver)
                    else:
                        pips[name] = info.get("version")
                else:
                    if name in pkgs:
                        my_ver = info.get("version")
                        old_ver = pkgs[name]
                        pkgs[name] = pick_version(old_ver, my_ver)
                    else:
                        pkgs[name] = info.get("version")

    print("+Pips (%s) for distro: %s" % (len(pips), distro))
    for name in sorted(pips.keys()):
        version = pips.get(name)
        if version is None:
            version = "???"
        else:
            version = str(version)
        print("[%s] with version [%s]" % (name, version))

    print("")
    print("+Packages (%s) for distro: %s" % (len(pkgs), distro))
    am_bad = len(pips.keys())
    for name in sorted(pkgs.keys()):
        version = pkgs.get(name)
        if version is None:
            version = "???"
        else:
            version = str(version)
        myver = versionize(version.strip("*").split("."))
        print("Would like [%s] with version [%s] or calculated version [%s]" % (name, version, myver))
        (found, fname, fver) = find_closest(name, version)
        if found:
            print("\tFound a satisfactory [%s] with calculated version [%s]" % (fname, fver))
        else:
            if fname is None:
                print("\tDid not find any package named [%s]" % (name))
                am_bad+=1
            else:
                print("\tOnly found [%s] at version [%s]" % (fname, fver))
                am_bad+=1
    print("Found %s missing or not good enough packages/pips" % (am_bad))
