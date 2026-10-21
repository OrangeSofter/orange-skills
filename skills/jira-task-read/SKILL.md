---
name: jira-task-read
description: >
  Read a Jira task description by its ID. Use when users 
  want to fetch, view, read, or pull a Jira issue/ticket/task
  description — for example "read RC-76490", "show me the Jira ticket"
  or any request that references a Jira task ID and needs its contents.
argument-hint: <JIRA_TASK_ID>
---

# Jira Task Read

Fetch the description of a Jira task.

`SKILL_DIR` = `{THIS_SKILL_DIRECTORY}` — the absolute path of this skill's folder.

---

## Input

The skill expects one argument:

1. **JIRA_TASK_ID** — the ticket identifier, e.g. `RC-76490`.

If the argument is missing, ask the user for the task ID before proceeding.

---

## Fetch the task

Run the bundled script, substituting the provided task ID:

```bash
bash $SKILL_DIR/scripts/get-jira-task.sh JIRA_TASK_ID --extract-description
```

## Output

Return the fetched task description as-is, preserving its structure.
