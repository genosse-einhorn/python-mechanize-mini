#!/usr/bin/env python3

import sys
import zipfile
import argparse
import importlib.util
import os
import stat

parser = argparse.ArgumentParser(description='Generates a python executable ZIP file from modules')
parser.add_argument('module', help="Modules to include in the zip file", nargs='+')
parser.add_argument('-o', '--output', help='Output file', required=True)
parser.add_argument('-m', '--main', help='Main module')

args = parser.parse_args()

# truncate existing file
with open(args.output, mode='w') as appzip:
    # possibly add shebang
    if args.main is not None:
        appzip.write("#!/usr/bin/env python3\n")

# possibly make it executable
if args.main is not None:
    st = os.stat(args.output)
    os.chmod(args.output, st.st_mode | ((st.st_mode & 0o444) >> 2))

# generate the zip file
with zipfile.ZipFile(args.output, mode='a') as appzip:
    for name in args.module:
        spec = importlib.util.find_spec(name)
        if spec is None:
            raise Exception("Can't find module `{}'".format(name))

        if not spec.has_location:
            raise Exception("Module `{}' has non-loadable location `{}'".format(name, spec.origin))

        if spec.origin.endswith('/__init__.py'):
            # this is a package, put the whole directory into the zip file

            dirprefix = name.replace('.', '/')
            srcpath = spec.origin.rsplit('/__init__.py', 1)[0]

            for dirpath, dirnames, filenames in os.walk(srcpath):
                for filename in filenames:
                    if filename[:1] == '.':
                        continue

                    filename = os.path.join(dirpath, filename)
                    relname = os.path.relpath(filename, srcpath)
                    appzip.write(filename, dirprefix + '/' + relname)

                if '__pycache__' in dirnames:
                    dirnames.remove('__pycache__')
        else:
            # import file
            appzip.write(spec.origin, name.replace('.', '/') + '.py')

    if args.main is not None:
        # write __main__.py
        mainpy = 'import runpy; runpy.run_module("{}", run_name="__main__")'.format(args.main)
        appzip.writestr('__main__.py', mainpy)
