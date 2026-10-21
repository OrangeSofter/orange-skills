---
name: jira-cli-direct-detailed
description: Command reference for jira (ankitpokhrel/jira-cli), covering issue search, viewing, creation, editing, assignment, status transitions, comments, worklogs, links, epics, sprints, projects, boards, and releases.
---

# Jira CLI command reference

This command-line interface (CLI) reference is based on the local help for `ankitpokhrel/jira-cli` version **1.7.0**. Command-specific help is available through `jira <command> <subcommand> --help`.

All keys such as `PRJ-123`, usernames, statuses, issue types, and numeric IDs below are examples. Available issue types, statuses, and field values depend on the Jira project.

## Configuration and diagnostics

| Command / option | Purpose |
| --- | --- |
| `jira version` | Display the CLI version. |
| `jira --help`, `jira issue edit --help` | Display general help or help for a specific operation. |
| `jira me` | Display the configured Jira user. |
| `jira serverinfo` | Retrieve information about the Jira instance. |
| `jira init` | Configure the connection interactively. |
| `-p PRJ`, `--project PRJ` | Select a project for the command instead of the configured default. |
| `-c /path/to/config.yml`, `--config /path/to/config.yml` | Select a configuration file. `JIRA_CONFIG_FILE` is also supported. |
| `--debug` | Enable diagnostic output. |

The default configuration path is `~/.config/.jira/.config.yml`. The main options for `jira init` are `--installation cloud\|local`, `--server`, `--login`, `--auth-type basic\|bearer\|mtls`, `--project`, and `--board`. Here, `\|` separates alternatives and is not a literal part of the value.

`init --force` overwrites the configuration, and `--insecure` disables TLS certificate verification.

The utility commands `completion` and `man` provide shell completion and man-page generation.

## Finding and reading issues

Issue lists are interactive by default. `--plain` produces a text table, while `--raw` produces JSON.

```bash
# Search for text within a project
jira issue list 'Authentication error' -p PRJ --plain

# Combine filters
jira issue list -p PRJ --type Bug --status 'In Progress' --label backend --plain

# JQL (Jira Query Language)
jira issue list -p PRJ --jql 'project = PRJ AND assignee = currentUser() ORDER BY updated DESC' --raw

# Pages with selected columns
jira issue list -p PRJ --paginate 0:50 --plain --columns key,summary,status,assignee
jira issue list -p PRJ --paginate 50:50 --plain --columns key,summary,status,assignee

# A single issue: text, comments, or the raw API response
jira issue view PRJ-123 --plain
jira issue view PRJ-123 --plain --comments 5
jira issue view PRJ-123 --raw
```

Main `issue list` options:

| Options | Purpose |
| --- | --- |
| `--type`, `--status`, `--priority`, `--resolution` | Issue type, status, priority, and resolution. `--status` can be repeated. |
| `--assignee`, `--reporter` | Assignee and reporter; `--assignee x` selects unassigned issues. |
| `--label`, `--component`, `--parent` | Label, component, and parent issue; `--label` can be repeated. |
| `--created`, `--updated` | Period: `today`, `week`, `month`, `year`, a date, or a relative value such as `--updated=-10d`. |
| `--created-after`, `--created-before`, `--updated-after`, `--updated-before` | Date boundaries. `--created` and `--updated` take precedence over their corresponding boundaries. |
| `--history`, `--watching` | Recently viewed or watched issues. |
| `--jql`, `-q` | JQL query; a `project = PRJ` clause restricts the search to a project. |
| `--order-by`, `--reverse` | Sort field (default: `created`) and reversal of the default descending order. |
| `--paginate OFFSET:LIMIT` | Page offset and size; the help specifies a maximum of 100 per request and a default of `0:100`. |
| `--plain`, `--raw`, `--csv` | Text table, JSON, or CSV output. |
| `--columns`, `--no-headers`, `--no-truncate`, `--delimiter` | Table settings with `--plain`: columns, headers, all available columns, and delimiter. |

`issue list` columns: `TYPE`, `KEY`, `SUMMARY`, `STATUS`, `ASSIGNEE`, `REPORTER`, `PRIORITY`, `RESOLUTION`, `CREATED`, `UPDATED`, `LABELS`. The issue description is available through `issue view`, not as a list column. By default, `issue view` shows one comment, not the entire discussion history.

`--paginate OFFSET:LIMIT` selects a result page. `--raw` does not disable pagination.

## Creating and editing issues

```bash
jira issue create -p PRJ --type Task --summary 'Add validation' --body 'Issue description' --no-input --raw

# A subtask requires a parent key and an issue type supported by the project
jira issue create -p PRJ --type Sub-task --parent PRJ-123 --summary 'Write tests' --body 'Verify the main scenario' --no-input

# Read the description from a file; --template - reads standard input
jira issue create -p PRJ --type Task --summary 'Prepare a report' --template /path/to/description.txt --no-input

jira issue edit PRJ-123 --summary 'Updated summary' --body 'New description' --no-input
jira issue edit PRJ-123 --label backend --label reviewed --no-input
jira issue edit PRJ-123 --label=-obsolete --no-input
```

The main options shared by `create` and `edit` are `--summary`, `--body`, `--priority`, `--assignee`, `--parent`, repeatable `--label`, `--component`, `--fix-version`, `--affects-version`, and `--custom key=value`. Custom field names and accepted values depend on configuration.

`create` also supports `--type`, `--reporter`, `--original-estimate`, `--template`, and `--raw`. `--body` takes precedence over `--template`. For `edit`, the description can be passed through stdin; its 1.7.0 help does not list `--template` or `--raw`.

In `edit`, labels are **appended**, components are **replaced**, and `fix-version` and `affects-version` values are appended. To remove a label, component, or fixVersion, the help specifies a value prefixed with `-`, such as `--label=-obsolete`. `--body` replaces the entire description.

`--no-input` disables prompts for optional fields but does not supply required values. Required fields depend on the project. `edit` supports `--skip-notify` to suppress update notifications. `--web` opens a browser after the operation.

## Assignee and status

```bash
jira issue assign PRJ-123 'user@example.com'
jira issue assign PRJ-123 default
jira issue assign PRJ-123 x
jira issue move PRJ-123 'In Progress'
jira issue move PRJ-123 Done --resolution Fixed
```

- `assign ISSUE-KEY ASSIGNEE`: requires an exact email or display-name match; `default` selects the default assignee, and `x` unassigns the issue. `jira me` returns the configured user for self-assignment.
- `move ISSUE-KEY STATE`: transitions the issue to a status; it does not move the issue to another project. Availability depends on the current state, workflow, and permissions.
- `move` supports `--assignee`, `--resolution`, and `--comment`. Neither `move` nor `assign` supports `--no-input`.

## Comments, worklogs, and watchers

```bash
jira issue comment add PRJ-123 'Verification completed' --no-input
jira issue comment add PRJ-123 --template /path/to/comment.txt --no-input
jira issue worklog add PRJ-123 '1h 30m' --no-input
jira issue worklog add PRJ-123 '1h' --started '2026-09-22 09:30:00' --timezone Europe/Moscow --comment 'Verifying the fix' --no-input
jira issue watch PRJ-123 'user@example.com'
```

- `comment add ISSUE-KEY [COMMENT_BODY]`: adds a comment; `--template -` reads stdin. Positional text takes precedence over the template. `--internal` creates an internal comment where Jira supports it.
- `worklog add ISSUE-KEY TIME_SPENT`: records time spent in a format such as `2d 1h 30m`. `--started` sets the start of the work; `--timezone` accepts an IANA time zone name and defaults to UTC. `--new-estimate` changes the remaining estimate.
- `watch ISSUE-KEY WATCHER`: adds a watcher using an exact email or display-name match.

In this version, the `comment` and `worklog` groups provide only `add`; editing and deleting entries are not supported by these command groups.

## Links, cloning, and deletion

```bash
jira issue link PRJ-123 PRJ-456 Blocks
jira issue unlink PRJ-123 PRJ-456
jira issue link remote PRJ-123 'https://example.com/design' 'Design document'
jira issue clone PRJ-123 --summary 'Issue copy'
jira issue delete PRJ-123
```

- `link INWARD_ISSUE_KEY OUTWARD_ISSUE_KEY ISSUE_LINK_TYPE`: links two issues. The arguments specify the inward issue, outward issue, and exact Jira link type name. Available types depend on Jira configuration; `Blocks` and `Duplicate` are examples.
- `unlink INWARD_ISSUE_KEY OUTWARD_ISSUE_KEY`: removes the link between the specified issues; there is no link type argument.
- `link remote ISSUE_KEY WEBLINK_URL WEBLINK_TITLE`: adds an external link.
- `clone ISSUE-KEY`: creates a copy. Overrides are available through `--parent`, `--summary`, `--priority`, `--assignee`, `--label`, and `--component`; repeatable `--replace 'old:new'` replaces text in the summary and description.
- `delete ISSUE-KEY`: deletes an issue. `--cascade` also deletes its subtasks.

These commands do not support `--no-input`.

## Epics

```bash
jira epic list -p PRJ --table --plain
jira epic list PRJ-100 --plain
jira epic create -p PRJ --name 'New account area' --summary 'Update the account area' --body 'Epic description' --no-input
jira epic add PRJ-100 PRJ-123 PRJ-456
jira epic remove PRJ-123 PRJ-456
```

- `epic list` displays epics, while `epic list EPIC-KEY` displays the epic's issues. `--table --plain` displays the epic list as a text table; filters, JQL, pagination, and output formats are available as documented in the command's help. The help limits the initial list to 100 epics.
- `epic create`: `--name` and `--summary` are separate fields. Description, assignee, reporter, priority, labels, components, versions, original estimate, custom fields, and description templates are also supported. This command's help does not list `--raw`.
- `epic add EPIC-KEY ISSUE-1 ...`: adds issues to an epic.
- `epic remove ISSUE-1 ...`: removes the assigned epic from issues; **the arguments are issue keys, without an epic key**.
- The help specifies a maximum of 50 issues per call for `add` and `remove`.

## Sprints

```bash
jira sprint list --table --plain --state active,future
jira sprint list 123 --plain
jira sprint list --current --plain
jira sprint add 123 PRJ-123 PRJ-456
jira sprint close 123
```

- `sprint list` retrieves sprints from the configured board; the help says it displays the first 50. `--state` accepts comma-separated `future`, `active`, and `closed`, with a default of `active,closed`.
- `sprint list SPRINT_ID` retrieves a sprint's issues. `--current`, `--prev`, and `--next` select issues in the current, previous, or next sprint. `--show-all-issues` includes issues from other projects.
- Sprint table columns are `ID`, `NAME`, `START`, `END`, `COMPLETE`, and `STATE`; sprint issues use issue columns. `--plain`, `--raw`, `--csv`, `--paginate`, JQL, and several filters are supported; see the help for the exact set.
- `sprint add SPRINT_ID ISSUE-1 ...` adds at most 50 issues per call. The sprint argument is a numeric ID, not a sprint name or epic key.
- `sprint close SPRINT_ID` closes the sprint.

CLI 1.7.0 has no `sprint create`, `sprint start`, or `sprint remove` subcommands.

## Projects, boards, releases, and URLs

```bash
jira project list
jira board list -p PRJ
jira release list -p PRJ
jira open PRJ-123 --no-browser
```

`project list` displays accessible projects; `board list` displays project boards; `release list` displays project versions. In 1.7.0, these groups support listing only: creating releases or boards is unsupported. None of these three commands supports `--plain` or `--raw`.

`jira open [ISSUE-KEY]` opens an issue in the browser, or the project page when no key is provided. `--no-browser` returns the URL without launching a browser.

## Reference sources

Syntax sources: `jira --help` and the installed version's subcommand help; project documentation: <https://github.com/ankitpokhrel/jira-cli>. `issue list` declares `--delimiter`; one example in the 1.7.0 help contains the typo `--delimeter`.

Operation availability, required fields, permissions, and allowed status transitions depend on the Jira server configuration.
