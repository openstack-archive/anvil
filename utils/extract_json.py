import json
import os
import sys
    
if __name__ == "__main__":
    me = os.path.basename(sys.argv[0])
    if len(sys.argv) == 1:
        print("%s filename filename filename..." % (me))
        sys.exit(0)
    fn = sys.argv[1]
    with open(fn, "r") as f:
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
    sys.exit(0)
