#!/usr/bin/env python3
"""Export a live Jira issue's native changelog to CSV or JSON.

Reads the Jira Cloud REST API with your own credentials and writes a clean
timeline: issue key, timestamp, author, field, from value, to value.

Nothing is uploaded anywhere. The script talks only to your own Jira site
and writes only to the output file (or stdout) you choose.

Environment variables:
    JIRA_SITE       e.g. https://your-site.atlassian.net
    JIRA_EMAIL      the email of your Atlassian account
    JIRA_API_TOKEN  an API token from https://id.atlassian.com/manage-profile/security/api-tokens

Usage:
    python3 jira_issue_history_exporter.py --issue PROJ-123
    python3 jira_issue_history_exporter.py --jql "project = PROJ ORDER BY key" --format json -o timeline.json

Limits of the native API (facts, not features):
    A deleted issue returns nothing from the API. Its changelog is destroyed
    with it, so this script cannot see deleted issues at all.
"""

import argparse
import base64
import csv
import io
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

CHANGELOG_PAGE_SIZE = 100


class JiraError(Exception):
    """Raised when the Jira API returns an error response."""


class IssueNotFound(JiraError):
    """Raised when an issue key returns 404 (deleted or never existed)."""


def build_auth_header(email, token):
    raw = "{}:{}".format(email, token).encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def make_fetcher(site, email, token):
    """Return a fetch(path) -> dict callable bound to one Jira site."""
    site = site.rstrip("/")
    headers = {
        "Authorization": build_auth_header(email, token),
        "Accept": "application/json",
    }

    def fetch(path):
        url = site + path
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise IssueNotFound("not found: {}".format(path))
            body = exc.read().decode("utf-8", "replace")[:300]
            raise JiraError("HTTP {} for {}: {}".format(exc.code, path, body))
        except urllib.error.URLError as exc:
            raise JiraError("could not reach {}: {}".format(site, exc.reason))

    return fetch


def fetch_changelog(fetch, issue_key):
    """Fetch every changelog page for one issue and return the histories."""
    histories = []
    start_at = 0
    while True:
        path = "/rest/api/3/issue/{}/changelog?startAt={}&maxResults={}".format(
            urllib.parse.quote(issue_key, safe=""), start_at, CHANGELOG_PAGE_SIZE
        )
        page = fetch(path)
        values = page.get("values", [])
        histories.extend(values)
        total = page.get("total", len(histories))
        start_at += len(values)
        if not values or start_at >= total:
            return histories


def search_issue_keys(fetch, jql):
    """Run a JQL search and return the matching issue keys, in order."""
    keys = []
    start_at = 0
    while True:
        params = urllib.parse.urlencode(
            {"jql": jql, "startAt": start_at, "maxResults": 100, "fields": "key"}
        )
        page = fetch("/rest/api/3/search?" + params)
        issues = page.get("issues", [])
        keys.extend(issue["key"] for issue in issues)
        total = page.get("total", len(keys))
        start_at += len(issues)
        if not issues or start_at >= total:
            return keys


def flatten_changelog(issue_key, histories):
    """Turn changelog histories into flat timeline rows."""
    rows = []
    for history in histories:
        author = ""
        author_obj = history.get("author") or {}
        author = author_obj.get("displayName") or author_obj.get("emailAddress") or ""
        created = history.get("created", "")
        for item in history.get("items", []):
            rows.append(
                {
                    "issue_key": issue_key,
                    "timestamp": created,
                    "author": author,
                    "field": item.get("field", ""),
                    "from_value": item.get("fromString") or "",
                    "to_value": item.get("toString") or "",
                }
            )
    rows.sort(key=lambda r: r["timestamp"])
    return rows


def rows_to_csv(rows):
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=["issue_key", "timestamp", "author", "field", "from_value", "to_value"],
    )
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def rows_to_json(rows):
    return json.dumps(rows, indent=2) + "\n"


def collect_rows(fetch, issue_keys, warn):
    """Fetch and flatten rows for each key; warn (not fail) on missing keys."""
    all_rows = []
    for key in issue_keys:
        try:
            histories = fetch_changelog(fetch, key)
        except IssueNotFound:
            warn(
                "warning: {} returned nothing from the API. If it was deleted, "
                "the native API holds no record of it at all.".format(key)
            )
            continue
        all_rows.extend(flatten_changelog(key, histories))
    return all_rows


def main(argv=None, fetch=None, warn=None):
    parser = argparse.ArgumentParser(
        description="Export a live Jira issue's native changelog to CSV or JSON."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--issue", help="a single issue key, e.g. PROJ-123")
    group.add_argument("--jql", help='a JQL query, e.g. "project = PROJ ORDER BY key"')
    parser.add_argument("--format", choices=["csv", "json"], default="csv")
    parser.add_argument("-o", "--output", help="output file (default: stdout)")
    args = parser.parse_args(argv)

    if warn is None:
        warn = lambda msg: print(msg, file=sys.stderr)

    if fetch is None:
        site = os.environ.get("JIRA_SITE")
        email = os.environ.get("JIRA_EMAIL")
        token = os.environ.get("JIRA_API_TOKEN")
        missing = [
            name
            for name, value in (
                ("JIRA_SITE", site),
                ("JIRA_EMAIL", email),
                ("JIRA_API_TOKEN", token),
            )
            if not value
        ]
        if missing:
            parser.error(
                "missing environment variable(s): {}".format(", ".join(missing))
            )
        fetch = make_fetcher(site, email, token)

    if args.issue:
        keys = [args.issue]
    else:
        keys = search_issue_keys(fetch, args.jql)

    rows = collect_rows(fetch, keys, warn)
    text = rows_to_csv(rows) if args.format == "csv" else rows_to_json(rows)

    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
