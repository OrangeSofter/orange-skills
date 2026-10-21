#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || -z "${1:-}" || "$1" == -* ]]; then
    printf 'Usage: %s JIRA-KEY\n' "$0" >&2
    exit 2
fi

for dependency in jira jq; do
    if ! command -v "$dependency" >/dev/null 2>&1; then
        printf 'Command not found: %s\n' "$dependency" >&2
        exit 127
    fi
done

jira_task_id=$1

jira issue move "$jira_task_id" Development >&2
jira issue edit "$jira_task_id" --label ai_agent --no-input >&2
jira issue view "$jira_task_id" --raw | jq -r '
    .fields.description
    | if . == null or . == "" then "No description available" else . end
'
