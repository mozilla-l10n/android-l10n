#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from collections import defaultdict
from reference_linter import StringExtraction, merge_errors
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
        total = 0
        for filename, ids in error_json.items():
            output.append(f"\n### File: {filename}")
            for id, error_messages in ids.items():
                full_id = f"{filename}:{id}"
                output.append(
                    f"\n**ID**: `{id}`"
                    f"\n**Previous:** `{errors[full_id]['previous']}`"
                    f"\n**New**: `{errors[full_id]['new']}`"
                )
                output.append("**Error:**")
                for e in error_messages:
                    output.append(f"- {e}")
                    total += 1
        output.append(f"\n**Total number of changed IDs:** {total}\n")

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

            merged_content = merge_errors(error_json, previous_content)
            with open(json_file, "w") as f:
                json.dump(merged_content, f, indent=2, sort_keys=True)

        # Print errors anyway on screen
        print("\n".join(output))
        sys.exit(1)
    else:
        print("No unchanged IDs found.")


if __name__ == "__main__":
    main()
