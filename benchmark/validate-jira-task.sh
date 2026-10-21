#!/usr/bin/env bash
set -euo pipefail

key=${1:?Usage: validate-jira-task.sh JIRA-KEY}

if ! jira issue view "$key" --raw | jq -e '
    .fields.status.name == "Development" and (.fields.labels | index("ai_agent") != null)
' >/dev/null; then
    echo "$key: Validation failed; expected status Development and label ai_agent." >&2
    exit 1
fi

echo "$key: verified — status Development, ai_agent present."
