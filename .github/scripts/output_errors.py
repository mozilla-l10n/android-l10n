#! /usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# This script output errors from a JSON file to a TXT file.

from reference_linter import outputErrors
import argparse
import json
import os
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--json",
        dest="json_file",
        help="Path to JSON file with errors info",
        required=True,
    )
    parser.add_argument(
        "--dest",
        dest="dest_file",
        help="Path to dest TXT file",
        required=True,
    )
    args = parser.parse_args()

    if not os.path.isfile(args.json_file):
        errors = {}
    else:
        with open(args.json_file, "r") as f:
            errors = json.load(f)
    if not errors:
        print("No errors found.")
        sys.exit(0)

    output = outputErrors(errors)
    with open(args.dest_file, "w") as f:
        f.writelines(output)


if __name__ == "__main__":
    main()
