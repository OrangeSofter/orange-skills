---
name: jira-start-task-mcp
description: Start work on a Jira issue. Use when the user asks to work on a Jira issue.
---

# Start Work on a Jira Issue via MCP

Input: `jira_task_id` — the Jira issue key, for example `RC-123`. If the key is missing, ask for it before accessing Jira.

## Procedure
Transition the issue to Development, add the ai_agent label, then retrieve its description and return it
as the result.
