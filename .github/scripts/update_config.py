#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


from import_strings import getReferenceFilesToml
from reference_linter import HTMLStripper
import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET


def check_string_quotes(text, rule):
    quote = "'" if rule == "IncorrectStraightQuote" else '"'
    html_stripper = HTMLStripper()
    html_stripper.clear()
    html_stripper.feed(text)
    cleaned_text = html_stripper.get_data()
    if quote in cleaned_text:
        return True

    return False


def main():
    # Read command line input parameters
    cl_parser = argparse.ArgumentParser()
    cl_parser.add_argument(
        "--toml",
        required=True,
        dest="toml_path",
        help="Path to l10n.toml file in the repository",
    )
    cl_parser.add_argument(
        "--ref",
        default="en-US",
        dest="reference_locale",
        help="Code for reference locale",
        nargs="?",
    )
    cl_parser.add_argument(
        "--config",
        nargs="?",
        dest="config_file",
        help="Path to JSON file with extra config (exceptions, brand names, etc.)",
    )
    args = cl_parser.parse_args()

    config_file = args.config_file
    if not os.path.exists(config_file):
        sys.exit(f"Config file {config_file} does not exist.")
    else:
        try:
            with open(config_file) as f:
                config = json.load(f)
        except Exception as e:
            sys.exit(e)

    ref_files = getReferenceFilesToml(args.toml_path, args.reference_locale)
    xml_lint = {
        # "IncorrectEllipsisCharacter": "",
        "IncorrectStraightQuote": "single_quotes",
        "IncorrectStraightDoubleQuote": "double_quotes",
        "BrandUsage": "brand",
    }

    for ref_file in ref_files:
        try:
            tree = ET.parse(ref_file["abs_path"])
            root = tree.getroot()
            for string in root.findall("string"):
                string_id = f"{ref_file['rel_path']}:{string.attrib['name']}"
                tools_ignore = [
                    rule.strip()
                    for rule in string.attrib.get(
                        "{http://schemas.android.com/tools}ignore", ""
                    ).split(",")
                    if rule.strip() in xml_lint.keys()
                ]
                for rule in tools_ignore:
                    # For quotes, skip if it's just HTML markup
                    if "Quote" in rule and not check_string_quotes(string.text, rule):
                        continue
                    list = config["exceptions"][xml_lint[rule]]
                    if string_id not in list:
                        list.append(string_id)
        except ET.ParseError as e:
            print(f"Error parsing XML file: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")

    with open(config_file, "w") as f:
        json.dump(config, f, indent=4, sort_keys=True)


if __name__ == "__main__":
    main()
