#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Examples:

Copy source files in l10n repo
python import_strings.py source --toml firefox-android/android-components/l10n.toml --dest android-l10n/mozilla-mobile/android-components

Copy localized files in code repo
python import_strings.py l10n --toml android-l10n/mozilla-mobile/android-components/l10n.toml --dest firefox-android/android-components
"""

from compare_locales import parser
from moz.l10n.paths import L10nConfigPaths, get_android_locale
import argparse
import os
import shutil


def getL10nFilesToml(toml_path):
    """Extract list of localized files from project configuration (TOML)"""

    basedir = os.path.dirname(toml_path)
    project_config_paths = L10nConfigPaths(
        toml_path, locale_map={"android_locale": get_android_locale}
    )

    l10n_files = []
    locales = list(project_config_paths.all_locales)
    locales.sort()
    for locale in locales:
        print(f"Creating list of files for locale: {locale}.")
        locale_files = [
            tgt_path.format(android_locale=get_android_locale(locale))
            for (ref_path, tgt_path), locales in project_config_paths.all().items()
        ]
        # Exclude missing files
        l10n_files.extend(
            [
                {
                    "abs_path": os.path.abspath(path),
                    "rel_path": os.path.relpath(path, basedir),
                }
                for path in locale_files
                if os.path.exists(path)
            ]
        )

    return l10n_files


def getReferenceFilesToml(toml_path, reference_locale):
    """Extract list of reference files from project configuration (TOML)"""

    basedir = os.path.dirname(toml_path)
    project_config_paths = L10nConfigPaths(
        toml_path, locale_map={"android_locale": get_android_locale}
    )

    print(f"Getting list of files for reference locale ({reference_locale}).")
    reference_files = [
        {
            "abs_path": os.path.abspath(ref_path.format(android_locale=None)),
            "rel_path": os.path.relpath(ref_path.format(android_locale=None), basedir),
        }
        for (ref_path, tgt_path), locales in project_config_paths.all().items()
    ]

    return reference_files


def copyL10nFiles(l10n_files, dest_path):
    """Copy localized files in code repository"""

    print(f"Files to copy: {len(l10n_files)}.")
    for l10n_file in l10n_files:
        l10n_relative = l10n_file["rel_path"]
        print(f"- {l10n_relative}.")

        dest_file = os.path.join(dest_path, l10n_relative)
        # Make sure that the folder exists, then copy file as is
        os.makedirs(os.path.dirname(dest_file), exist_ok=True)
        shutil.copy2(l10n_file["abs_path"], dest_file)


def copyReferenceFiles(reference_files, dest_path):
    """Copy reference files in l10n repository"""

    print(f"Files to copy: {len(reference_files)}.")
    for ref_file in reference_files:
        ref_relative = ref_file["rel_path"]
        print(f"- {ref_relative}.")

        # Parse the file and write it back in the new destination
        p = parser.getParser(ref_relative)
        p.readFile(ref_file["abs_path"])
        entities = p.walk()
        dest_file = os.path.join(dest_path, ref_relative)
        # Create folder if missing
        os.makedirs(os.path.dirname(dest_file), exist_ok=True)
        with open(dest_file, "w") as f:
            f.write("".join(entity.all for entity in entities))


def copyTomlFile(toml_path, dest_path):
    """Copy TOML file"""

    # Copy the TOML file, assuming it goes in the root of the destination path
    toml_name = os.path.basename(toml_path)
    print(f"\nCopying {toml_name} to {dest_path}")
    shutil.copy2(toml_path, os.path.join(dest_path, toml_name))


def main():
    # Read command line input parameters
    cl_parser = argparse.ArgumentParser()
    cl_parser.add_argument(
        dest="action",
        choices=["source", "l10n"],
        help="Action: source (to import source files), l10n (to export localized files)",
    )
    cl_parser.add_argument(
        "--toml",
        required=True,
        dest="toml_path",
        help="Path to l10n.toml file in the repository",
    )
    cl_parser.add_argument(
        "--dest",
        dest="dest_path",
        help="Path where to store updated localization files",
    )
    cl_parser.add_argument(
        "--ref",
        default="en-US",
        dest="reference_locale",
        help="Code for reference locale",
        nargs="?",
    )
    args = cl_parser.parse_args()

    if args.action == "l10n":
        l10n_files = getL10nFilesToml(args.toml_path)
        copyL10nFiles(l10n_files, args.dest_path)
    else:
        reference_files = getReferenceFilesToml(args.toml_path, args.reference_locale)
        copyReferenceFiles(reference_files, args.dest_path)

    copyTomlFile(args.toml_path, args.dest_path)


if __name__ == "__main__":
    main()
