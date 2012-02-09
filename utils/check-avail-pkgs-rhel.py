import json
import os
import sys
import re
import subprocess

#useful for running like the following
#find conf/ | grep ".json\$" | xargs python utils/check-avail.py "rhel-6"
#on a rhel6 system


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


def versionize(ver, maxlen=5):
    real_digits = list()
    for i in range(maxlen):
        if i < len(ver):
            digit = ver[i].strip().strip("*")
            if not len(digit):
                real_digits.append("0")
            else:
                real_digits.append(digit)
        else:
            real_digits.append("0")
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
    tmp = re.compile(r"^([\d]*):(.*)$", re.IGNORECASE)
    for line in lines:
        line = line.strip()
        g = tmp.match(line)
        if g:
            line = g.group(2)
        if line.startswith(name):
            founds.append(line)
    possibles = list()
    for found in founds:
        pieces = found.split(":", 1)
        if len(pieces) >= 1:
            poss = pieces[0].strip()
            if poss:
                possibles.append(poss)
    myver = versionize(version.strip("*").split("."))
    versions_found = dict()
    prog = re.compile(r"^([\d\.]*)(.*el6.*)$", re.IGNORECASE)
    for p in possibles:
        if p.startswith(name):
            verinfo = p[len(name):len(p)]
            verinfo = verinfo.strip("-")
            g = prog.match(verinfo)
            if g:
                v = g.group(1)
                aver = versionize(v.strip("*").split("."))
                if aver is not None and aver not in versions_found:
                    versions_found[p] = aver
    if not versions_found:
        return (False, None, None)
    else:
        for (name, version) in versions_found.items():
            if version >= myver:
                return (True, name, version)
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
        cmd = ['yum', 'provides', pkgname]
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
            return (False, None, None)
    except OSError:
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
