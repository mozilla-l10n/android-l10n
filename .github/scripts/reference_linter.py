#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# This script analyzes the reference files for errors.
#
# If a --json parameter is provided, the script will exit with status 0 and save
# error data into a JSON file (content will be appended if the file already
# exists). Otherwise, errors will be printed on screen and the script will exit
# with return value 1.

from collections import defaultdict
from compare_locales.parser import getParser
from html.parser import HTMLParser
from moz.l10n.paths import L10nConfigPaths, get_android_locale
import argparse
import copy
import json
import os
import sys


class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.fed = []

    def clear(self):
        self.reset()
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return " ".join(self.fed)


class StringExtraction:
    def __init__(self, toml_path):
        """Initialize object."""

        self.ref_strings = {}
        self.toml_path = toml_path

    def extractStrings(self):
        """Extract strings using TOML configuration."""

        basedir = os.path.dirname(self.toml_path)
        project_config_paths = L10nConfigPaths(
            self.toml_path, locale_map={"android_locale": get_android_locale}
        )

        reference_files = [
            ref_path.format(android_locale=None)
            for (ref_path, tgt_path), locales in project_config_paths.all().items()
        ]
        for reference_file in reference_files:
            key_path = os.path.relpath(reference_file, basedir)
            try:
                p = getParser(reference_file)
            except UserWarning:
                continue

            p.readFile(reference_file)
            self.ref_strings.update(
                (
                    f"{key_path}:{entity.key}",
                    entity.raw_val,
                )
                for entity in p.parse()
            )

        print(f"{len(self.ref_strings)} strings extracted")

    def getTranslations(self):
        """Return dictionary with translations"""

        return self.ref_strings


class QualityCheck:
    def __init__(self, ref_strings, config_path, toml_path):
        self.ref_strings = ref_strings
        self.config_path = config_path
        self.toml_path = toml_path
        self.errors = {toml_path: defaultdict(dict)}

        self.runChecks()

    def runChecks(self):
        """Check translations for issues"""

        def storeError(string_id, error_msg):
            filename, id = string_id.split(":")
            if id in self.errors[self.toml_path].get(filename, {}):
                self.errors[self.toml_path][filename][id]["errors"].append(error_msg)
            else:
                self.errors[self.toml_path][filename][id] = {
                    "text": self.ref_strings[string_id],
                    "errors": [error_msg],
                }

        def ignoreString(exceptions, errorcode, string_id):
            """Check if a string should be ignored"""

            if not exceptions:
                return False

            if string_id in exceptions.get(errorcode, []):
                return True

            return False

        # Load config
        if not self.config_path:
            exceptions = {}
            brands = []
        else:
            try:
                with open(self.config_path) as f:
                    config = json.load(f)
                    exceptions = config["exceptions"]
                    brands = config["brands"]
            except Exception as e:
                sys.exit(e)

        html_stripper = HTMLStripper()
        for ref_id, ref_string in self.ref_strings.items():
            # Ignore strings excluded from all checks
            if ignoreString(exceptions, "general", ref_id):
                continue

            # Check for empty strings
            if ref_string == "":
                storeError(ref_id, f"{ref_id} is empty")

            # Check for 3 dots instead of ellipsis
            if "..." in ref_string:
                storeError(
                    ref_id, "Incorrect ellipsis character `...`. Use `…` instead."
                )

            # Check for straight single quotes
            if "'" in ref_string and not ignoreString(
                exceptions, "single_quotes", ref_id
            ):
                storeError(
                    ref_id, "Incorrect straight quote character `'`. use `’` instead."
                )

            # Check for straight double quotes
            if '"' in ref_string and not ignoreString(
                exceptions, "double_quotes", ref_id
            ):
                # Check if the version without HTML is clean
                html_stripper.clear()
                html_stripper.feed(ref_string)
                cleaned_str = html_stripper.get_data()
                if '"' in cleaned_str:
                    storeError(
                        ref_id,
                        'Incorrect straight double quote character `"`. use `“”` instead.',
                    )

            # Check for hard-coded brand names:
            if not ignoreString(exceptions, "brand", ref_id):
                for brand in brands:
                    if brand in ref_string:
                        storeError(
                            ref_id,
                            f"Hard-coded brand `{brand}`. Use a variable instead.",
                        )


def outputErrors(errors):
    """Print error messages"""

    output = []
    for config_name, config_errors in errors.items():
        if config_errors:
            output.append(f"\n## TOML file: {config_name}")
        total = 0
        for filename, ids in config_errors.items():
            output.append(f"\n### File: {filename}")
            for id, file_data in ids.items():
                output.append(f"\n**ID**: `{id}`")
                output.append(f"**Text**: `{file_data['text']}`")
                output.append("**Errors:**")
                for e in file_data["errors"]:
                    output.append(f"- {e}")
                    total += 1
        if total > 0:
            output.append(f"\n**Total errors not yet reported:** {total}\n")

    return "\n".join(output)


def mergeErrors(new_content, old_content):
    merged_content = copy.deepcopy(new_content)
    for config_name, config_errors in old_content.items():
        if config_name not in merged_content:
            merged_content[config_name] = {}
        for filename, string_ids in config_errors.items():
            if filename not in merged_content[config_name]:
                merged_content[config_name][filename] = {}
            for string_id, file_data in string_ids.items():
                if string_id in merged_content[config_name][filename]:
                    # Assume the text in the same, only add the errors (removing duplicates).
                    merged_errors = list(
                        set(
                            file_data["errors"]
                            + merged_content[config_name][filename][string_id]["errors"]
                        )
                    )
                    merged_content[config_name][filename][string_id]["errors"] = (
                        merged_errors
                    )
                else:
                    merged_content[config_name][filename][string_id] = file_data

    return merged_content


def main():
    # Read command line input parameters
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--toml", required=True, dest="toml_path", help="Path to l10n.toml file"
    )
    parser.add_argument(
        "--json",
        default="errors.json",
        dest="json_file",
        help="Save error info as JSON to file",
    )
    parser.add_argument(
        "--config",
        nargs="?",
        dest="config_file",
        help="Path to JSON file with extra config (exceptions, brand names, etc.)",
    )
    args = parser.parse_args()

    extracted_strings = StringExtraction(args.toml_path)
    extracted_strings.extractStrings()
    ref_strings = extracted_strings.getTranslations()

    checks = QualityCheck(ref_strings, args.config_file, args.toml_path)

    has_errors = False
    for config_name, config_errors in checks.errors.items():
        if config_errors:
            has_errors = True
    if has_errors:
        output = outputErrors(checks.errors)
        print(output)

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

            merged_content = mergeErrors(checks.errors, previous_content)
            with open(json_file, "w") as f:
                json.dump(merged_content, f, indent=2, sort_keys=True)
        else:
            # Exit with status 1
            sys.exit(1)
    else:
        print("No issues found.")


if __name__ == "__main__":
    main()
