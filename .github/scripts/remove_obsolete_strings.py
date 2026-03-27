#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Remove <string> elements with moz:removedIn attribute equal to a given version
from all strings.xml files in values/ directories, and remove those string IDs
from _data JSON files.

Usage:
    python scripts/remove_obsolete_strings.py <repo_root> <version>

Example:
    python scripts/remove_obsolete_strings.py . 150
"""

import argparse
import glob
import json
import os
import sys

from moz.l10n.resource import parse_resource, serialize_resource
from moz.l10n.model import Entry

MOZ_REMOVED_IN = "{http://mozac.org/tools}removedIn"


def process_file(file_path, version_str):
    """Remove entries with moz:removedIn == version_str. Returns list of removed IDs."""
    with open(file_path, "+rb") as file:
        res = parse_resource(file_path, file.read())
        removed_ids = []

        for section in res.sections:
            kept = []
            for entry in section.entries:
                if isinstance(entry, Entry) and any(
                    m.key == MOZ_REMOVED_IN and m.value == version_str
                    for m in entry.meta
                ):
                    removed_ids.append(entry.id[0])
                else:
                    kept.append(entry)
            section.entries = kept

        if removed_ids:
            file.seek(0)
            for line in serialize_resource(res):
                file.write(line.encode("utf-8"))
            file.truncate()

    return removed_ids


def update_data_json(repo_root, removed_ids_by_rel_path):
    """Remove string IDs from _data/*.json files."""
    data_files = glob.glob(
        os.path.join(repo_root, "_data", "**", "*.json"), recursive=True
    )

    for data_file in sorted(data_files):
        with open(data_file) as f:
            data = json.load(f)

        changed = False
        for rel_path, ids_to_remove in removed_ids_by_rel_path.items():
            if rel_path in data:
                before = data[rel_path]
                data[rel_path] = [s for s in before if s not in ids_to_remove]
                if len(data[rel_path]) != len(before):
                    changed = True

        if changed:
            with open(data_file, "w") as f:
                json.dump(data, f, indent=2, sort_keys=True)
                f.write("\n")
            print(f"  Updated _data: {os.path.relpath(data_file, repo_root)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="Root path of the repository")
    parser.add_argument("version", type=int, help="Version number (e.g. 150)")
    args = parser.parse_args()

    repo_root = os.path.abspath(args.path)
    version_str = str(args.version)

    if not os.path.isdir(repo_root):
        sys.exit(f"Error: '{repo_root}' is not a directory")

    pattern = os.path.join(repo_root, "**/values/strings.xml")
    files = sorted(glob.glob(pattern, recursive=True))

    if not files:
        print("No strings.xml files found.")
        return

    removed_from_source: dict[str, set[str]] = {}
    total_strings = 0
    total_files = 0

    for file_path in files:
        removed_ids = process_file(file_path, version_str)
        if not removed_ids:
            continue

        rel_path = os.path.relpath(file_path, repo_root)
        print(f"  {rel_path}: removed {len(removed_ids)} string(s)")
        total_strings += len(removed_ids)
        total_files += 1
        removed_from_source[rel_path] = set(removed_ids)

    if removed_from_source:
        print()
        update_data_json(repo_root, removed_from_source)

    print(f"\nDone: removed {total_strings} string(s) from {total_files} file(s).")


if __name__ == "__main__":
    main()
