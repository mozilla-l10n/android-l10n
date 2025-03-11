#! /usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# This script searches for string IDs in the code repository, then uses GitHub
# APIs to blame the file and identify the author of the last change. Authors are
# then CCed to the pull request by adding a comment.
#
# Limitations: the script currently has mozilla-mobile/firefox-android
# hard-coded as code repository, and assumes that removing `mozilla-mobile/` at
# the start of a string ID is enough to find the file in that repository.

from collections import defaultdict
from reference_linter import outputErrors
import argparse
import json
import os
import re
import shutil
import sys
import requests
import urllib.request
import zipfile


class QueryPR:
    def __init__(self, api_token):
        """Initialize object."""

        self.api_token = api_token
        self.owner = "mozilla"
        self.repository = "gecko-dev"

    def set_pr_data(self, owner, repository, pr_number):
        self.pr_owner = owner
        self.pr_repository = repository
        self.pr_number = int(pr_number)

    def api_request(self, query):
        url = "https://api.github.com/graphql"
        json_query = {"query": query}
        headers = {"Authorization": f"token {self.api_token}"}
        r = requests.post(url=url, json=json_query, headers=headers)

        return r.json()

    def extract_errors_artifact(self, run_id):
        url = f"https://api.github.com/repos/{self.pr_owner}/{self.pr_repository}/actions/artifacts"
        headers = {"Authorization": f"token {self.api_token}"}
        r = requests.get(url=url, headers=headers)
        try:
            json_data = r.json()["artifacts"]
        except Exception:
            return {}

        errors = {}
        file_url = None
        for artifact in json_data:
            # Each run only has one artifact
            if str(artifact["workflow_run"]["id"]) == run_id:
                file_url = artifact["archive_download_url"]

        if file_url:
            tmp_folder = "tmp_artifacts"
            os.makedirs(tmp_folder, exist_ok=True)
            local_artifact_path = os.path.join(tmp_folder, "errors.zip")
            # Save artifact as errors.zip
            with requests.get(url=file_url, headers=headers, stream=True) as response:
                with open(local_artifact_path, "wb") as f:
                    shutil.copyfileobj(response.raw, f)

            if not os.path.exists(local_artifact_path):
                print(
                    f"There was an error downloading the artifact: {local_artifact_path}"
                )
                return errors

            # Extract the ZIP file in a temporary folder
            with zipfile.ZipFile(local_artifact_path, "r") as z:
                z.extractall(tmp_folder)

            json_path = os.path.join(tmp_folder, "errors.json")
            if os.path.exists(json_path):
                with open(json_path, "r") as f:
                    errors = json.load(f)

            # Remove the temporary folder
            shutil.rmtree(tmp_folder)

        return errors

    def get_authors(self, errors):
        # Get the full list of authors based on the errors
        self.authors = []
        for config_name, config_errors in errors.items():
            for filepath, string_ids in config_errors.items():
                self.lines = []
                # Need to manually change the path to match gecko-dev
                filepath = filepath.removeprefix("mozilla-mobile/")
                filepath = f"mobile/android/{filepath}"
                for string_id in string_ids:
                    n = self.find_string_line(filepath, string_id)
                    self.lines.append(n)
                self.lines.sort()
                self.find_lines_author(filepath)
        self.authors.sort()

        print(f"Authors: {', '.join(self.authors)}")
        # Exclude authors that are already involved in the PR
        self.exclude_mentioned_authors()
        if self.authors:
            print(f"Remaining authors: {', '.join(self.authors)}")
        else:
            print("All authors already CCed.")

        return self.authors

    def find_string_line(self, filepath, string_id):
        # Find the line number where the string ID is defined
        # In the XML, strings are defined as name="ID"

        url = f"https://raw.githubusercontent.com/{self.owner}/{self.repository}/main/{filepath}"
        data = urllib.request.urlopen(url)
        for n, line in enumerate(data):
            if f'name="{string_id}"' in line.decode("utf-8"):
                return n + 1

        return 0

    def find_lines_author(self, filepath):
        # Use GraphQL to blame the file and identify the author for a specific line number

        query = """
            {
            repository(owner: "%OWNER%", name: "%REPO%") {
                ref(qualifiedName: "main") {
                target {
                    ... on Commit {
                    blame(path: "%PATH%") {
                        ranges {
                        commit {
                            author {
                            user {
                                login
                            }
                            }
                        }
                        startingLine
                        endingLine
                        }
                    }
                    }
                }
                }
            }
            }
        """
        filepath = filepath.lstrip("/")
        query = (
            query.replace("%OWNER%", self.owner)
            .replace("%REPO%", self.repository)
            .replace("%PATH%", filepath)
        )

        r = self.api_request(query)

        ranges = r["data"]["repository"]["ref"]["target"]["blame"]["ranges"]

        current_line_index = 0
        for range in ranges:
            if self.lines[current_line_index] <= range["endingLine"]:
                try:
                    author = range["commit"]["author"]["user"]["login"]
                except Exception:
                    author = None
                if author and author not in self.authors:
                    self.authors.append(author)
                current_line_index += 1
                if current_line_index >= len(self.lines):
                    return

    def query_comments(self, order="first", size=100):
        # Query comments, either first or last

        query = """
        {
            repository(owner: "%OWNER%", name: "%REPO%") {
            pullRequest(number: %PR_NUMBER%) {
                comments(%ORDER%: %SIZE%) {
                nodes {
                    author {
                    login
                    }
                    body
                }
                }
            }
            }
        }
        """
        query = (
            query.replace("%OWNER%", self.pr_owner)
            .replace("%REPO%", self.pr_repository)
            .replace("%PR_NUMBER%", str(self.pr_number))
            .replace("%ORDER%", order)
            .replace("%SIZE%", str(size))
        )

        return self.api_request(query)

    def exclude_mentioned_authors(self):
        # Exclude authors that are already mentioned in comments in the PR

        r = self.query_comments()
        comments = r["data"]["repository"]["pullRequest"]["comments"]["nodes"]
        for comment in comments:
            # Check if the author already commented
            if comment["author"]["login"] in self.authors:
                self.authors.remove(comment["author"]["login"])

            # Check if the author is mentioned in the body of the comment
            comment_body = comment["body"]
            for author in self.authors[:]:
                if f"@{author}" in comment_body:
                    self.authors.remove(author)

            # If the list of authors is empty, return early
            if not self.authors:
                return

    def exclude_reported_errors(self, new_errors):
        # Exclude errors that were already mentioned in comments in the PR

        r = self.query_comments("last", 25)
        comments = r["data"]["repository"]["pullRequest"]["comments"]["nodes"]

        id_pattern = re.compile(r"Run ID: ([0-9]*)")
        run_id = None
        for comment in comments:
            # Check if the comment was generated by automation, and find the
            # associated run ID
            matches = id_pattern.findall(comment["body"])
            if matches:
                run_id = matches[0]

        # If there are no comments generated by automation, we can return early,
        # as all errors are missing.
        if not run_id:
            return new_errors

        # Even if there are multiple comments generated by automation, we only
        # care about the results from the last run
        reported_errors = self.extract_errors_artifact(run_id) if run_id else {}

        missing_errors = defaultdict(lambda: defaultdict(dict))
        for config_name, config_errors in new_errors.items():
            for filename, ids in config_errors.items():
                for id, file_data in ids.items():
                    for error in file_data["errors"]:
                        reported_errors_id = (
                            reported_errors.get(config_name, {})
                            .get(filename, {})
                            .get(id, {})
                            .get("errors", [])
                        )
                        if error not in reported_errors_id:
                            if id in missing_errors[config_name][filename]:
                                missing_errors[config_name][filename].append(error)
                            else:
                                missing_errors[config_name][filename][id] = {
                                    "errors": [error],
                                    "text": file_data["text"],
                                }

        return missing_errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", dest="token", help="API Token", required=True)
    parser.add_argument("--repo", dest="repo", help="Repository name", required=True)
    parser.add_argument(
        "--owner", dest="owner", help="Owner of the repository", required=True
    )
    parser.add_argument(
        "--pr", dest="pr_number", help="Number of the current PR", required=True
    )
    parser.add_argument(
        "--run", dest="run_id", help="ID of GitHub action run", required=True
    )
    parser.add_argument(
        "--json",
        default="errors.json",
        dest="json_file",
        help="Path to JSON file with errors info",
    )
    parser.add_argument(
        "--dest",
        default="comment.txt",
        dest="dest_file",
        help="Path to dest file with comment content",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.json_file):
        errors = {}
    else:
        with open(args.json_file, "r") as f:
            errors = json.load(f)
    if not errors:
        print("No errors found.")
        sys.exit(0)

    query_pr = QueryPR(args.token)
    query_pr.set_pr_data(args.owner, args.repo, args.pr_number)
    authors = query_pr.get_authors(errors)
    missing_errors = query_pr.exclude_reported_errors(errors)

    output = []
    if authors:
        line = "Authors: "
        for author in authors:
            line = f"{line} @{author}"
        output.append(f"{line}\n")

    output += outputErrors(missing_errors)

    if output:
        output.insert(0, f"Run ID: {args.run_id}\n")
        with open(args.dest_file, "w") as f:
            f.writelines(output)
    else:
        print("All errors are already reported")


if __name__ == "__main__":
    main()
