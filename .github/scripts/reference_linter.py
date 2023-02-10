#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
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
        self.error_messages = []

        self.runChecks()

    def runChecks(self):
        """Check translations for issues"""

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

        for ref_id, ref_string in self.ref_strings.items():
            # Ignore strings excluded from all checks
            if ignoreString(exceptions, "general", ref_id):
                continue

            # Check for empty strings
            if ref_string == "":
                error_msg = f"{ref_string} is empty"
                self.error_messages.append(error_msg)

            # Check for 3 dots instead of ellipsis
            if "..." in ref_string:
                error_msg = f"'...' in {ref_id}\n" f"  Text: {ref_string}"
                self.error_messages.append(error_msg)

            # Check for hard-coded brand names:
            if not ignoreString(exceptions, "brand", ref_id):
                for brand in brands:
                    if brand in ref_string:
                        error_msg = (
                            f"Brand '{brand}' hard-coded in {ref_id}\n"
                            f"  Text: {ref_string}"
                        )
                        self.error_messages.append(error_msg)

    def printErrors(self, toml_name):
        """Print error messages"""

        output = []
        if self.error_messages:
            output.append(
                f"\n\nTOML file: {toml_name}"
                f"\nErrors: {len(self.error_messages)}"
            )
            for e in self.error_messages:
                output.append(f"\n  {e}")

        return output


def main():
    # Read command line input parameters
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--toml", required=True, dest="toml_path", help="Path to l10n.toml file"
    )
    parser.add_argument("--ref", dest="reference_code", help="Reference language code")
    parser.add_argument("--dest", dest="dest_file", help="Save output to file")
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
                f.write("\n".join(output))
        # Print errors anyway on screen
        print("\n".join(output))
        sys.exit(1)
    else:
        print("No issues found.")


if __name__ == "__main__":
    main()
