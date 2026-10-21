---
name: jira-start-task-cli
description: Start work on a Jira issue. Use when the user asks to work on a Jira issue.
---

# Start Work on a Jira Issue

Input: `jira_task_id` — the Jira issue key, for example `RC-123`. If the key is missing, ask for it before accessing Jira.

## Procedure
The script moves the Jira issue to `Development`, adds the `ai_agent` label, and prints the issue description.

Run [scripts/start-task.sh](scripts/start-task.sh), passing the issue key as the only argument. Resolve the path relative to this skill's directory:

```bash
bash scripts/start-task.sh RC-123
```
