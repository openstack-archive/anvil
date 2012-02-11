import json
import os
import sys


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
        output = json.dumps(data, indent=4, sort_keys=True)
        print(output)


if __name__ == "__main__":
    ME = os.path.basename(sys.argv[0])
    if len(sys.argv) == 1:
        print("%s filename filename filename..." % (ME))
        sys.exit(0)
    clean_file(sys.argv[1])
    sys.exit(0)
