#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || ! ${1:-} =~ ^[A-Z][A-Z0-9_]*-[1-9][0-9]*$ ]]; then
    printf 'Usage: %s JIRA-KEY\n' "$0" >&2
    exit 2
fi
for dependency in jira jq; do
    command -v "$dependency" >/dev/null 2>&1 || { echo "Command not found: $dependency" >&2; exit 127; }
done
exec </dev/null
key=$1
trap 'echo "$key: reset not confirmed (line $LINENO)." >&2; exit 1' ERR

read_issue() {
    jira issue view "$key" --raw | jq -ce --arg key "$key" '
        if .key == $key and (.fields.status.name | type == "string" and length > 0)
            and (.fields.labels | type == "array" and all(.[]; type == "string"))
        then [.fields.status.name, (.fields.labels | unique)]
        else error("Invalid Jira response") end'
}

before=$(read_issue)
expected=$(jq -c '.[0] = "New" | .[1] -= ["ai_agent"]' <<< "$before")
if [[ $(jq -r '.[0]' <<< "$before") != New ]]; then
    jira issue move "$key" New >&2
fi
if jq -e '.[1] | index("ai_agent") != null' <<< "$before" >/dev/null; then
    jira issue edit "$key" --label=-ai_agent --no-input >&2
fi
after=$(read_issue)
if [[ "$after" != "$expected" ]]; then
    echo "$key: Final verification failed: $after; expected $expected" >&2
    exit 1
fi
echo "$key [${BENCHMARK_PHASE:-standalone}, iteration ${BENCHMARK_ITERATION:-—}]: verified — status New, ai_agent absent, other labels preserved."
