#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# This script detects string change between two folders.
#
# If a --json parameter is provided, the script will exit with status 0 and save
# error data into a JSON file (content will be appended if the file already
# exists). Otherwise, errors will be printed on screen and the script will exit
# with return value 1.

from collections import defaultdict
from reference_linter import StringExtraction, mergeErrors, outputErrors
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
    parser.add_argument(
        "--json",
        default="errors.json",
        dest="json_file",
        help="Save error info as JSON to file",
    )
    args = parser.parse_args()

    def normalize_keys(strings, root_path):
        """Return a copy of strings with file paths made relative to root_path."""
        normalized = {}
        for key, value in strings.items():
            file_path, string_id = key.split(":", 1)
            rel_path = os.path.relpath(file_path, root_path)
            normalized[f"{rel_path}:{string_id}"] = value
        return normalized

    toml_path = args.toml_path
    base = StringExtraction(os.path.join(args.base_path, toml_path))
    base.extractStrings()
    base_strings = normalize_keys(base.getTranslations(), args.base_path)

    head = StringExtraction(os.path.join(args.head_path, toml_path))
    head.extractStrings()
    head_strings = normalize_keys(head.getTranslations(), args.head_path)

    # Find differences
    errors = {
        key: {"previous": base_strings[key], "new": head_strings[key]}
        for key in base_strings.keys()
        if key in head_strings
        and base_strings[key]["value"] != head_strings[key]["value"]
    }

    errors_json = {toml_path: defaultdict(dict)}
    for string_id in errors.keys():
        filename, id = string_id.split(":")
        error_msg = f"String was changed without a new ID. Previous value: `{errors[string_id]['previous']['value']}`"
        if id in errors_json[toml_path].get(filename, {}):
            errors_json[toml_path][filename]["errors"][id].append(error_msg)
        else:
            errors_json[toml_path][filename][id] = {
                "errors": [error_msg],
                "value": errors[string_id]["new"]["value"],
                "comment": errors[string_id]["new"].get("comment", ""),
            }

    has_errors = False
    for config_name, config_errors in errors_json.items():
        if config_errors:
            has_errors = True
    if has_errors:
        output = outputErrors(errors_json)
        print(output)

        # Check if there's a JSON output specified
        json_file = args.json_file
        if json_file:
            print(f"Saving output to {json_file}")
            if os.path.exists(json_file):
                try:
                    with open(json_file, "r") as f:
                        previous_content = json.load(f)
                except Exception:
                    previous_content = {}
            else:
                previous_content = {}

            merged_content = mergeErrors(errors_json, previous_content)
            with open(json_file, "w") as f:
                json.dump(merged_content, f, indent=2, sort_keys=True)
        else:
            # Exit with status 1
            sys.exit(1)
    else:
        print("No unchanged IDs found.")


if __name__ == "__main__":
    main()
