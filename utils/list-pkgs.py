import json
import os
import sys

#useful for running like the following
#find conf/ | grep ".json\$" | xargs python utils/list-pkgs.py "rhel-6"

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


def update_version(distro, old_ver, new_ver):
    if new_ver is None:
        return old_ver
    if old_ver is None:
        return new_ver
    try:
        cleaned_old = old_ver.strip("*")
        cleaned_new = new_ver.strip("*")
        #TODO this may not always work, oh well
        #ie 1.7 is not less than 1.6.3 :-P
        cleaned_old = "".join(cleaned_old.split("."))
        cleaned_new = "".join(cleaned_new.split("."))
        old_v = float(cleaned_old)
        new_v = float(cleaned_new)
        if old_v < new_v:
            return new_ver
        else:
            return old_ver
    except ValueError:
        return old_ver


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
                        pips[name] = update_version(distro, old_ver, my_ver)
                    else:
                        pips[name] = info.get("version")
                else:
                    if name in pkgs:
                        my_ver = info.get("version")
                        old_ver = pkgs[name]
                        pkgs[name] = update_version(distro, old_ver, my_ver)
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
    for name in sorted(pkgs.keys()):
        version = pkgs.get(name)
        if version is None:
            version = "???"
        else:
            version = str(version)
        print("[%s] with version [%s]" % (name, version))

