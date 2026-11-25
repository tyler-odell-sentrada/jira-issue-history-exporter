import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import jira_issue_history_exporter as exporter


HISTORY = {
    "id": "10001",
    "author": {"displayName": "Ada Admin", "emailAddress": "ada@example.com"},
    "created": "2026-01-02T10:00:00.000+0000",
    "items": [
        {"field": "status", "fromString": "To Do", "toString": "In Progress"},
        {"field": "assignee", "fromString": None, "toString": "Ada Admin"},
    ],
}


def fake_fetch_factory(pages):
    """pages maps a path prefix to a list of response dicts (popped in order)."""

    def fetch(path):
        for prefix, responses in pages.items():
            if path.startswith(prefix):
                if not responses:
                    raise AssertionError("no more fake responses for " + path)
                return responses.pop(0)
        raise AssertionError("unexpected path " + path)

    return fetch


class FlattenTests(unittest.TestCase):
    def test_flattens_items_to_rows(self):
        rows = exporter.flatten_changelog("PROJ-1", [HISTORY])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["issue_key"], "PROJ-1")
        self.assertEqual(rows[0]["author"], "Ada Admin")
        self.assertEqual(rows[0]["field"], "status")
        self.assertEqual(rows[0]["from_value"], "To Do")
        self.assertEqual(rows[0]["to_value"], "In Progress")
        self.assertEqual(rows[1]["from_value"], "")

    def test_rows_sorted_by_timestamp(self):
        later = dict(HISTORY, created="2026-02-01T00:00:00.000+0000")
        rows = exporter.flatten_changelog("PROJ-1", [later, HISTORY])
        self.assertEqual(rows[0]["timestamp"], "2026-01-02T10:00:00.000+0000")


class ChangelogPaginationTests(unittest.TestCase):
    def test_follows_pagination(self):
        page1 = {"values": [HISTORY], "total": 2, "startAt": 0, "maxResults": 1}
        page2 = {"values": [HISTORY], "total": 2, "startAt": 1, "maxResults": 1}
        fetch = fake_fetch_factory({"/rest/api/3/issue/PROJ-1/changelog": [page1, page2]})
        histories = exporter.fetch_changelog(fetch, "PROJ-1")
        self.assertEqual(len(histories), 2)


class SearchTests(unittest.TestCase):
    def test_search_returns_keys(self):
        page = {"issues": [{"key": "PROJ-1"}, {"key": "PROJ-2"}], "total": 2}
        fetch = fake_fetch_factory({"/rest/api/3/search": [page]})
        self.assertEqual(exporter.search_issue_keys(fetch, "project = PROJ"), ["PROJ-1", "PROJ-2"])


class OutputTests(unittest.TestCase):
    def test_csv_has_header_and_rows(self):
        rows = exporter.flatten_changelog("PROJ-1", [HISTORY])
        text = exporter.rows_to_csv(rows)
        lines = text.strip().splitlines()
        self.assertEqual(lines[0], "issue_key,timestamp,author,field,from_value,to_value")
        self.assertEqual(len(lines), 3)

    def test_json_round_trips(self):
        rows = exporter.flatten_changelog("PROJ-1", [HISTORY])
        parsed = json.loads(exporter.rows_to_json(rows))
        self.assertEqual(parsed[0]["field"], "status")


class MissingIssueTests(unittest.TestCase):
    def test_missing_issue_warns_and_continues(self):
        def fetch(path):
            if "PROJ-9" in path:
                raise exporter.IssueNotFound("gone")
            return {"values": [HISTORY], "total": 1}

        warnings = []
        rows = exporter.collect_rows(fetch, ["PROJ-9", "PROJ-1"], warnings.append)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(warnings), 1)
        self.assertIn("PROJ-9", warnings[0])


class AuthTests(unittest.TestCase):
    def test_auth_header_is_basic_base64(self):
        header = exporter.build_auth_header("ada@example.com", "token123")
        self.assertTrue(header.startswith("Basic "))
        import base64

        decoded = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
        self.assertEqual(decoded, "ada@example.com:token123")


if __name__ == "__main__":
    unittest.main()
