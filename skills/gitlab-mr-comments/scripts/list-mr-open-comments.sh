#!/bin/bash

set -u

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  echo "Usage: list-mr-open-comments.sh [--help | --format]"
  echo ""
  echo "Lists open (unresolved) review comments on the current branch's MR."
  echo ""
  echo "Options:"
  echo "  --help, -h    Show this help message"
  echo "  --format      Show the output format description"
  echo ""
  echo "Requirements:"
  echo "  - glab CLI installed and authenticated: https://docs.gitlab.com/cli/"
  echo "  - jq installed"
  exit 0
fi

if [ "${1:-}" = "--format" ]; then
  echo "Each thread is separated by ---"
  echo "Thread lines:"
  echo "  - <comment_id>       (first 8 chars of discussion ID)"
  echo "  - <file_path>:<line> (or '_no file path_' for general comments)"
  echo "  - @<author>          (commenter username)"
  echo "    > <comment_body>   (quoted, one line per source line)"
  echo "  - @<reply_author>    (if replies exist)"
  echo "    > <reply_body>"
  exit 0
fi

if ! command -v glab >/dev/null 2>&1; then
  echo "Failed to list MR comments: 'glab' CLI is not installed."
  echo "glab: https://docs.gitlab.com/cli/"
  echo "Surface this to the user clearly — don't try to work around it."
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "Failed to list MR comments: 'jq' is not installed."
  echo "Install jq (e.g. 'brew install jq') and retry."
  exit 1
fi

# glab mr note ищет и в закрытых мр, поэтому явно передаем id открытого мр
MR_ID=$(glab mr list -F json --jq '.[].iid')
MR_ID_COUNT=$(echo "$MR_ID" | grep -c '[^[:space:]]')

if [ "$MR_ID_COUNT" -eq 0 ]; then
  echo "No open merge request available for the current branch."
  echo "Surface that message to the user as-is rather than treating it as an error."
  exit 0
fi

if [ "$MR_ID_COUNT" -gt 1 ]; then
  echo "Failed to list MR comments: multiple open merge requests found for the current branch."
  echo "Expected exactly one open MR, but got: $(echo "$MR_ID" | paste -sd ',' -)"
  echo "Surface this to the user clearly — don't try to work around it."
  exit 1
fi

NOTES_OUTPUT=$(glab mr note list "$MR_ID" --state unresolved -F json 2>&1)
NOTES_STATUS=$?

strip_ansi() {
  sed $'s/\033\[[0-9;]*m//g'
}

if [ $NOTES_STATUS -ne 0 ]; then
  # Most common "soft" failure: "No open merge request available for <branch>".
  # Pass it through as-is and exit 0 — there's nothing to list, not an error.
  if echo "$NOTES_OUTPUT" | grep -q "No open merge request available"; then
    echo "$NOTES_OUTPUT" \
      | strip_ansi \
      | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' \
      | grep -v '^$' \
      | grep -v '^ERROR$'
      echo "Surface that message to the user as-is rather than treating it as an error."
    exit 0
  fi
  echo "Failed to fetch MR discussions:"
  echo "$NOTES_OUTPUT"
  exit 1
fi

NOTES_JSON=$(echo "$NOTES_OUTPUT" | strip_ansi)

if ! echo "$NOTES_JSON" | jq -e 'type == "array"' >/dev/null 2>&1; then
  echo "Failed to parse MR discussions as JSON:"
  echo "$NOTES_OUTPUT"
  exit 1
fi

# Drop discussions where every note is a system note (assignments, label changes, etc.).
ACTIONABLE=$(echo "$NOTES_JSON" | jq '[ .[] | select(any(.notes[]?; (.system // false) | not)) ]')

TOTAL_COUNT=$(echo "$ACTIONABLE" | jq 'length')

if [ "$TOTAL_COUNT" = "0" ]; then
  echo "No open review comments on this MR."
  exit 0
fi

FILTER='
  def render_note:
    "- @\(.author.username // .author.name // "unknown")\n"
    + ((.body // "") | split("\n") | map("  > " + .) | join("\n"));

  def render_thread:
    (.notes | map(select((.system // false) | not))) as $real
    | if ($real | length) == 0 then ""
      else
        $real[0] as $first
        | ($real[1:] | map(render_note) | join("\n\n")) as $replies
        | ($first | render_note)
          + (if ($replies | length) > 0 then "\n\n" + $replies else "" end)
      end;

  map(
    (.id | .[0:8]) as $id
    | (.notes[0].position) as $p
    | (if $p then ($p.new_path // $p.old_path // null) else null end) as $path
    | (if $p then ($p.new_line // $p.old_line // null) else null end) as $line
    | "- \($id)\n"
      + "- \(if $path then ($path + (if $line then ":\($line)" else "" end)) else "_no file path_" end)\n"
      + render_thread
  )
  | join("\n\n---\n\n")
'

echo
echo "$ACTIONABLE" | jq -r "$FILTER"
echo
