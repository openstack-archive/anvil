"""
Searches the given path for JSON files, and validates their contents.

Optionally, replaces valid JSON files with their pretty-printed
counterparts.
"""

import errno
import json
import logging
import optparse
import os
import re


# Configure logging
logging.basicConfig(format='%(levelname)s: %(message)s')
ROOT_LOGGER = logging.getLogger("")
ROOT_LOGGER.setLevel(logging.WARNING)
LOGGER = logging.getLogger(__name__)

# Configure commandlineability
parser = optparse.OptionParser()
parser.add_option('-p', type="string", default=os.getcwd(),
    help='the path to search for JSON files', dest='path')
parser.add_option('-r', type="string", default='.json$',
    help='the regular expression to match filenames against ' \
        '(not absolute paths)', dest='regexp')
(args, _) = parser.parse_args()


def main():
    files = find_matching_files(args.path, args.regexp)
    results = True
    print("Validating %s json files (found using regex [%s] in path [%s])" % (len(files), args.regexp, args.path))
    for path in files:
        pres = validate_json(path)
        if not pres:
            print("Failed at validating [%s]" % (path))
            results = False
        else:
            print("Validated [%s]" % (path))
    # Invert our test results to produce a status code
    if results:
        exit(0)
    else:
        exit(1)


def validate_json(path):
    """Open a file and validate it's contents as JSON"""
    try:
        LOGGER.info("Validating %s" % (path))
        contents = read_file(path)
        if contents is False:
            logging.warning('Insufficient permissions to open: %s' % path)
            return False
    except:
        LOGGER.warning('Unable to open: %s' % path)
        return False

    #knock off comments
    ncontents = list()
    for line in contents.splitlines():
        tmp_line = line.strip()
        if tmp_line.startswith("#"):
            continue
        else:
            ncontents.append(line)

    contents = os.linesep.join(ncontents)
    try:
        jdict = json.loads(contents)
        if not type(jdict) is dict:
            LOGGER.error('Root element in %s is not a dictionary!' % path)
            return False
    except Exception:
        LOGGER.exception('Unable to parse: %s' % path)
        return False

    return True


def find_matching_files(path, pattern):
    """Search the given path for files matching the given pattern"""

    regex = re.compile(pattern)
    json_files = []
    for root, dirs, files in os.walk(path):
        for name in files:
            if regex.search(name):
                full_name = os.path.join(root, name)
                json_files.append(full_name)
    return json_files


def read_file(path):
    """Attempt to read a file safely

    Returns the contents of the file as a string on success, False otherwise"""
    try:
        fp = open(path)
    except IOError as e:
        if e.errno == errno.EACCES:
            # permission error
            return False
        raise
    else:
        with fp:
            return fp.read()


def replace_file(path, new_contents):
    """Overwrite the file at the given path with the new contents

    Returns True on success, False otherwise."""
    try:
        f = open(path, 'w')
        f.write(new_contents)
        f.close()
    except:
        LOGGER.error('Unable to write: %s' % f)
        return False
    return True


if __name__ == "__main__":
    main()
