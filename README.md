# Jira Issue History Exporter

Jira's issue history is partial, and a deleted issue is gone. This script exports what the native changelog does hold.

A free command-line tool that reads a live Jira issue's native changelog from the Jira Cloud REST API and writes a clean timeline to CSV or JSON: issue key, timestamp, author, field, from value, to value. It answers the auditor's question for issues that still exist, in one run, on your own machine.

## Run it

You need Python 3 (standard library only, nothing to install) and an Atlassian API token, which you can create at id.atlassian.com under Manage profile, Security, API tokens.

```bash
git clone https://github.com/tyler-odell-sentrada/jira-issue-history-exporter.git
cd jira-issue-history-exporter
export JIRA_SITE="https://your-site.atlassian.net"
export JIRA_EMAIL="you@example.com"
export JIRA_API_TOKEN="your-api-token"

# One issue, CSV to stdout
python3 jira_issue_history_exporter.py --issue PROJ-123

# A whole project, JSON to a file
python3 jira_issue_history_exporter.py --jql "project = PROJ ORDER BY key" --format json -o timeline.json
```

Sample output (CSV):

```csv
issue_key,timestamp,author,field,from_value,to_value
PROJ-123,2026-01-02T10:00:00.000+0000,Ada Admin,status,To Do,In Progress
PROJ-123,2026-01-02T10:00:00.000+0000,Ada Admin,assignee,,Ada Admin
PROJ-123,2026-01-05T09:31:00.000+0000,Ben Builder,priority,Medium,High
```

## What it cannot do

These are facts about Jira's native API, not features held back:

- **It cannot see a deleted issue at all.** A deleted issue returns nothing from the API, and its changelog is destroyed with it. There is no recycle bin, no snapshot, no restore, and no revert for deleted issues in the native record.
- **It captures nothing continuously.** A run shows only what Jira's native changelog still holds at that moment. Nothing is recorded between runs.
- **The native changelog is not the full record.** It does not carry the complete comment and worklog history of an issue, only field changes.
- **Restricted-visibility comments are outside it**, as they are for every tool on the platform. No API can read a comment whose visibility is restricted to a group or role you are not in.

If you need the history of an issue that has already been deleted, this script cannot help, and neither can any script: the data is gone from Jira. The only way to recover a deleted issue is to have captured it before the deletion happened.

## The app that does it continuously

[Issue History & Deleted Issue Recovery for Jira](https://marketplace.atlassian.com/apps/1637274584?utm_source=github&utm_medium=free-tool&utm_campaign=jira-history-exporter) records every change as it happens, keeps a complete snapshot of every issue, and keeps deleted issues in a recycle bin so they can be restored under a new key with their history stitched back in. It runs entirely inside Atlassian's infrastructure. If deleted issues are the risk you actually care about, that is the tool built for it.

## Housekeeping

- Runs entirely on your own credentials and your own machine. No data leaves your Jira site; the script talks only to your site and writes only to the output you choose.
- No telemetry, no run limits, no nag screens.
- Licence: MIT (see LICENSE).
