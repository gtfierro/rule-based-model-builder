"""
"""
import sys
import json

def find_templates(filename):
    with open(filename) as f:
        lines = [x.strip() for x in f.read().split('\n') if len(x)]

    templates = set()
    rows = []

    for line in lines:
        point_name, parts = line.split(' => ')
        parts = [x.strip().split(' -> ') for x in parts.split(';')]
        parts = {x[1]: x[0] for x in parts if len(x) == 2}
        keys = tuple(parts.keys())
        templates.add(keys)
        rows.append(parts)

    for template in sorted(templates):
        print(template)

    with open("rows.json", "w") as f:
        json.dump(rows, f)

if __name__ == '__main__':
    find_templates(sys.argv[1])
