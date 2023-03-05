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

from reference_linter import outputErrors
import argparse
import json
import os
import sys
import requests
import urllib.request


class QueryAuthors:
    def __init__(self, api_token):
        """Initialize object."""

        self.api_token = api_token
        self.owner = "mozilla-mobile"
        self.repository = "firefox-android"

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

    def get_authors(self, errors):
        # Get the full list of authors based on the errors
        self.authors = []
        for config_name, config_errors in errors.items():
            for filepath, string_ids in config_errors.items():
                self.lines = []
                # Need to manually remove part of the path
                filepath = filepath.lstrip("mozilla-mobile")
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
                except:
                    author = None
                if author and author not in self.authors:
                    self.authors.append(author)
                current_line_index += 1
                if current_line_index >= len(self.lines):
                    return

    def exclude_mentioned_authors(self):
        # Exclude authors that are already mentioned in comments in the PR

        query = """
        {
            repository(owner: "%OWNER%", name: "%REPO%") {
            pullRequest(number: %PR_NUMBER%) {
                comments(first: 100) {
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
        )

        r = self.api_request(query)
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

    query_authors = QueryAuthors(args.token)
    query_authors.set_pr_data(args.owner, args.repo, args.pr_number)
    authors = query_authors.get_authors(errors)

    if authors:
        line = "Authors: "
        for author in authors:
            line = f"{line} @{author}"
        output = [f"{line}\n"]
        output += outputErrors(errors)
        with open(args.dest_file, "w") as f:
            f.writelines(output)


if __name__ == "__main__":
    main()
