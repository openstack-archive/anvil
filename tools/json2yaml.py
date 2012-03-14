
import glob
import json
import os
import sys


def load_json(fn):
    with open(fn, 'r') as f:
        lines = f.readlines()
    data = os.linesep.join(
        l
        for l in lines
        if not l.lstrip().startswith('#')
        )
    return json.loads(data)

distro = sys.argv[1]

for input_file in glob.glob('conf/pkgs/*.json'):
    data = load_json(input_file)

    print
    print '    - name: %s' % os.path.splitext(os.path.basename(input_file))[0]
    print '      packages:'
    for pkg, info in sorted(data.get(distro, {}).items()):
        print '      - name: %s' % pkg
        for n, v in sorted(info.items()):
            print '        %s: %s' % (n, v)
