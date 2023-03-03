#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from collections import defaultdict
from reference_linter import StringExtraction
import argparse
import json
import os
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base",
        required=True,
        dest="base_path",
        help="Folder with the previous version of files (copied from base repository)",
    )
    parser.add_argument(
        "--head",
        required=True,
        dest="head_path",
        help="Folder with the new version of files (copied from head repository)",
    )
    parser.add_argument(
        "--toml",
        required=True,
        dest="toml_path",
        help="Path to l10n.toml file, relative to the root of the project folder",
    )
    parser.add_argument("--dest", dest="dest_file", help="Save error messages to file")
    parser.add_argument(
        "--json", dest="json_file", help="Save error info as JSON to file"
    )
    args = parser.parse_args()

    base = StringExtraction(os.path.join(args.base_path, args.toml_path))
    base.extractStrings()
    base_strings = base.getTranslations()

    head = StringExtraction(os.path.join(args.head_path, args.toml_path))
    head.extractStrings()
    head_strings = head.getTranslations()

    # Find differences
    errors = {
        key: {"previous": base_strings[key], "new": head_strings[key]}
        for key in base_strings.keys()
        if key in head_strings and base_strings[key] != head_strings[key]
    }

    error_json = defaultdict(dict)
    for string_id in errors.keys():
        filename, id = string_id.split(":")
        error_msg = "String was changed without a new ID"
        if id in error_json.get(filename, {}):
            error_json[filename][id].append(error_msg)
        else:
            error_json[filename][id] = [error_msg]

    if errors:
        output = []
        total = len(list(errors.keys()))
        for id, values in errors.items():
            output.append(
                f"\nID: {id}"
                f"\nPrevious: {values['previous']}"
                f"\nNew: {values['new']}"
            )
        output.append(f"\nTotal number of changed IDs: {total}")

        out_file = args.dest_file
        if out_file:
            print(f"Saving output to {out_file}")
            if os.path.exists(out_file):
                with open(out_file, "r") as f:
                    previous_content = f.readlines()
            else:
                previous_content = []

            with open(out_file, "w") as f:
                f.writelines(previous_content)
                f.write("\n")
                f.write("\n".join(output))

        # Check if there's a JSON output specified
        json_file = args.json_file
        if json_file:
            print(f"Saving output to {json_file}")
            if os.path.exists(json_file):
                try:
                    with open(json_file, "r") as f:
                        previous_content = json.load(f)
                except:
                    previous_content = {}
            else:
                previous_content = {}

            previous_content.update(checks.error_json)
            with open(json_file, "w") as f:
                json.dump(previous_content, f, indent=2, sort_keys=True)

        # Print errors anyway on screen
        print("\n".join(output))
        sys.exit(1)
    else:
        print("No unchanged IDs found.")


if __name__ == "__main__":
    main()
