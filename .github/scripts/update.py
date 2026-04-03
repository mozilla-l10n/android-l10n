# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Update the localization source files from an Android-related branch, adding new files and
messages. For updates from the "{HEAD}" branch, also update changed messages.

Writes a summary of the branch's localized files and message keys as
`_data/[project]/[branch].json`, and a commit message summary as `.update_msg`.
"""

import json
from argparse import ArgumentParser
from filecmp import cmp
from os import makedirs, pardir
from os.path import abspath, dirname, exists, join, relpath
from shutil import copy
from sys import exit
from typing import TypedDict

from moz.l10n.formats import UnsupportedFormat
from moz.l10n.paths import L10nConfigPaths
from moz.l10n.resource import (
    add_entries,
    parse_resource,
    serialize_resource,
)
from moz.l10n.model import Entry


class AutomationConfig(TypedDict):
    branches: list[str]
    head: str
    paths: dict[str, str]


def update(
    cfg_automation: AutomationConfig,
    project: str,
    branch: str,
    fx_root: str,
    repo_root: str,
):
    if branch not in cfg_automation["branches"]:
        exit(f"Unknown branch: {branch}")
    is_head = branch == cfg_automation["head"]
    if not exists(fx_root):
        exit(f"Firefox root not found: {fx_root}")
    print(f"source: {branch} at {fx_root}")
    fx_root = abspath(fx_root)

    source_files: set[str] = set()

    cfg_path = join(fx_root, cfg_automation["paths"][project], "l10n.toml")

    if not exists(cfg_path):
        exit(f"Config file not found: {cfg_path}")

    project_base_path = join(repo_root, "mozilla-mobile")
    paths = L10nConfigPaths(cfg_path)
    if branch == cfg_automation["head"]:
        dest_path = join(project_base_path, project)
        print(f"\nCopying l10n.toml to {relpath(dest_path, repo_root)}")
        copy(cfg_path, dest_path)

    messages: dict[str, list[str]] = {}
    new_files = 0
    updated_files = 0

    source_files = (fx_path for fx_path, _ in paths.all())
    for fx_path in source_files:
        dest_path = join(
            project_base_path,
            relpath(fx_path, fx_root).replace("mobile/android/", ""),
        )
        rel_path = relpath(dest_path, repo_root)

        makedirs(dirname(dest_path), exist_ok=True)

        try:
            fx_res = parse_resource(fx_path)
        except FileNotFoundError:
            print(f"source file not found: {fx_path}")
            continue
        except UnsupportedFormat:
            messages[rel_path] = []
            if not exists(dest_path):
                print(f"create {rel_path}")
                copy(fx_path, dest_path)
                new_files += 1
            elif branch == cfg_automation["head"] and not cmp(fx_path, dest_path):
                print(f"update {rel_path}")
                copy(fx_path, dest_path)
                updated_files += 1
            else:
                # print(f"skip {rel_path}")
                pass
            continue

        messages[rel_path] = [
            ".".join(section.id + entry.id)
            for section in fx_res.sections
            for entry in section.entries
            if isinstance(entry, Entry)
        ]

        if not exists(dest_path):
            print(f"create {rel_path}")
            with open(dest_path, "+wb") as file:
                for line in serialize_resource(fx_res):
                    file.write(line.encode("utf-8"))
            new_files += 1
        elif cmp(fx_path, dest_path):
            # print(f"equal {rel_path}")
            pass
        else:
            with open(dest_path, "+rb") as file:
                res = parse_resource(dest_path, file.read())
                if add_entries(res, fx_res, use_source_entries=is_head):
                    print(f"update {rel_path}")
                    file.seek(0)
                    for line in serialize_resource(res):
                        file.write(line.encode("utf-8"))
                    file.truncate()
                    updated_files += 1
                else:
                    # print(f"unchanged {rel_path}")
                    pass

    data_path = join(repo_root, "_data", project, f"{branch}.json")
    makedirs(dirname(data_path), exist_ok=True)
    with open(data_path, "w") as file:
        json.dump(messages, file, indent=2, sort_keys=True)

    return new_files, updated_files


def write_commit_msg(args, new_files: int, updated_files: int, repo_root: str):
    new_str = f"{new_files} new" if new_files else ""
    update_str = f"{updated_files} updated" if updated_files else ""
    summary = (
        f"{new_str} and {update_str}"
        if new_str and update_str
        else new_str or update_str or "no changes"
    )
    count = updated_files or new_files
    summary += " files" if count > 1 else " file" if count == 1 else ""
    head = f"{args.branch} ({args.commit})" if args.commit else args.branch
    with open(join(repo_root, ".update_msg"), "w") as file:
        file.write(f"{head}: {summary}")


if __name__ == "__main__":
    curr_dir = dirname(abspath(__file__))
    repo_root = abspath(join(curr_dir, pardir, pardir))
    config_file = join(repo_root, ".github", "update-config.json")

    with open(config_file) as f:
        cfg_automation = json.load(f)

    prog = "python .github/scripts/update.py"
    parser = ArgumentParser(
        prog=prog,
        description=__doc__.format(HEAD=cfg_automation["head"]),
        epilog=f"""Example: {prog} --project fenix --branch release
        --commit $(cd firefox && git rev-parse --short HEAD) --firefox firefox""",
    )
    parser.add_argument(
        "--project",
        required=True,
        choices=["fenix", "android-components", "focus-android"],
        help='The project identifier, e.g. "fenix", "android-components", or "focus-android".',
    )
    parser.add_argument(
        "--branch",
        required=True,
        help='The branch identifier, e.g. "main", "beta", or "release".',
    )
    parser.add_argument("--commit", help="A commit id for the branch.")
    parser.add_argument(
        "--firefox", required=True, help="Path to the root of the Firefox source tree."
    )
    args = parser.parse_args()

    new_files, updated_files = update(
        cfg_automation, args.project, args.branch, args.firefox, repo_root
    )

    write_commit_msg(args, new_files, updated_files, repo_root)
