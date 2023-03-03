#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from collections import defaultdict
from html.parser import HTMLParser
import argparse
import copy
import json
import os
import sys

try:
    from compare_locales import paths
    from compare_locales.parser import getParser
except ImportError as e:
    print("FATAL: make sure that dependencies are installed")
    print(e)
    sys.exit(1)


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

        project_config = paths.TOMLParser().parse(self.toml_path, env={"l10n_base": ""})
        files = paths.ProjectFiles(None, [project_config])
        basedir = os.path.dirname(self.toml_path)
        for l10n_file, reference_file, _, _ in files:
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
    def __init__(self, ref_strings, config_path):

        self.ref_strings = ref_strings
        self.config_path = config_path
        self.errors = defaultdict(dict)

        self.runChecks()

    def runChecks(self):
        """Check translations for issues"""

        def storeError(string_id, error_msg):
            filename, id = string_id.split(":")
            if id in self.errors.get(filename, {}):
                self.errors[filename][id].append(error_msg)
            else:
                self.errors[filename][id] = [error_msg]

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

    def printErrors(self, toml_name):
        """Print error messages"""

        output = []
        if self.errors:
            output.append(f"TOML file: {toml_name}\n")
            total = 0
            for filename, ids in self.errors.items():
                output.append(f"\n### File: {filename}")
                for id, errors in ids.items():
                    full_id = f"{filename}:{id}"
                    output.append(f"\n**ID**: `{id}`")
                    output.append(f"**Text**: `{self.ref_strings[full_id]}`")
                    output.append("**Errors:**")
                    for e in errors:
                        output.append(f"- {e}")
                        total += 1
            output.append(f"\n**Total errors in reference:** {total}\n")

        return "\n".join(output)


def merge_errors(new_content, old_content):

    merged_content = copy.deepcopy(new_content)
    for filename, ids in old_content.items():
        if filename not in merged_content:
            merged_content[filename] = {}
        for id, errors in ids.items():
            if id in merged_content[filename]:
                # Add errors to existing and remove duplicates
                errors += merged_content[filename][id]
                errors = list(set(errors))

            merged_content[filename][id] = errors

    return merged_content


def main():
    # Read command line input parameters
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--toml", required=True, dest="toml_path", help="Path to l10n.toml file"
    )
    parser.add_argument("--dest", dest="dest_file", help="Save error messages to file")
    parser.add_argument(
        "--json", dest="json_file", help="Save error info as JSON to file"
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

    checks = QualityCheck(ref_strings, args.config_file)
    output = checks.printErrors(os.path.basename(args.toml_path))
    if output:
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
                f.write(output)

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

            merged_content = merge_errors(checks.errors, previous_content)
            with open(json_file, "w") as f:
                json.dump(merged_content, f, indent=2, sort_keys=True)

        # Print errors anyway on screen
        print(output)
        sys.exit(1)
    else:
        print("No issues found.")


if __name__ == "__main__":
    main()
