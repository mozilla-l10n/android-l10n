#! /usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from glob import glob
import argparse
import os
import shutil


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        required=True,
        dest="source_locale",
        help="Locale code to use as source",
    )
    parser.add_argument(
        "--dest",
        required=True,
        dest="dest_locale",
        help="Locale code to use as destination",
    )
    parser.add_argument(
        "--path",
        required=True,
        dest="base_path",
        help="Path to the base folder including localized files",
    )
    parser.add_argument("locales", nargs="*", help="Locales to process")
    args = parser.parse_args()

    # Set variables from args
    base_path = args.base_path
    source_locale = args.source_locale
    source_folder = f"values-{source_locale.replace('-', '-r')}"
    dest_locale = args.dest_locale
    dest_folder = f"values-{dest_locale.replace('-', '-r')}"

    # Get a list of all the files for the source locale
    source_files = []
    for xml_path in glob(f"{base_path}/**/{source_folder}/*.xml", recursive=True):
        source_files.append(xml_path)
    if not source_files:
        sys.exit(f"No reference file found in {os.path.join(base_path, source_locale)}")

    # Copy the files to the destination locale
    for src_filename in source_files:
        dest_filename = src_filename.replace(f"{source_folder}", f"{dest_folder}")
        os.makedirs(os.path.dirname(dest_filename), exist_ok=True)
        shutil.copy(src_filename, dest_filename)


if __name__ == "__main__":
    main()
