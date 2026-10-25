from pathlib import Path
import os
import marshal

if not os.path.exists('dat'):
    os.makedirs('dat')

strings_set = set()

for file in Path('./extracted').rglob('*'):
    if file.is_file():
        name = str(file)
        file = open(file, 'rb').read()
        code = marshal.loads(file[16:])

        # get string literals
        strings = [
            obj.split(",")
            for obj in code.co_consts
            if isinstance(obj, str)
            and len(obj) > 0
            and obj.isprintable()
            and '.' in obj
        ]

        # flatten the list of lists
        strings = [s.strip() for sublist in strings for s in sublist]

        strings_set.update(strings)

with open('dat/strings.list', 'w') as f:
    for string in sorted(strings_set):
        f.write(f"{string}\n")
