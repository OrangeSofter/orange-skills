#!/bin/bash

if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
  echo "Usage: $0 <JIRA_TASK_ID> [--extract-description]"
  echo ""
  echo "Arguments:"
  echo "  JIRA_TASK_ID           The Jira issue key (e.g. RC-12345)"
  echo "  --extract-description  Print only the title and description in Markdown format"
  echo ""
  echo "Examples:"
  echo "  $0 RC-12345"
  echo "  $0 RC-12345 --extract-description"
  exit 0
fi

if [ -z "$1" ]; then
  echo "Usage: $0 <JIRA_TASK_ID> [--extract-description]"
  exit 1
fi

JIRA_TASK_ID="$1"
EXTRACT_MODE="$2"
TASK_OUTPUT=$(jira issue view "$JIRA_TASK_ID" --plain --comments 0 2>&1)

if [ $? -ne 0 ]; then
  echo "Failed to fetch Jira task: $JIRA_TASK_ID"
  echo "Ensure 'jira' CLI (ankitpokhrel/jira-cli) is installed and authenticated."
  echo "If the command fails because the tool is not installed or not configured, surface that to the user clearly — don't try to work around it."
  echo "If the command fails because of formatting error, try to run this script without --extract-description argument"
  exit 1
fi

if [ "$EXTRACT_MODE" != "--extract-description" ]; then
  echo "$TASK_OUTPUT"
  exit 0
fi

TITLE=$(echo "$TASK_OUTPUT" | grep -m1 '^  # ' | sed 's/^  # //' | sed 's/[[:space:]]*$//')
DESCRIPTION=$(echo "$TASK_OUTPUT" \
  | sed $'s/\033\[[0-9;]*m//g' \
  | awk '/^[[:space:]]*-+ Description -+[[:space:]]*$/{found=1; next} found && /^[[:space:]]*-+[[:space:]]/{found=0} found{print}' \
  | sed 's/^  //' \
  | sed 's/View this issue on Jira:.*//' \
  | sed 's/[[:space:]]*$//' \
  | grep -v '^[0-9]\{1,\}$')

printf "# %s\n\n%s\n" "$TITLE" "$DESCRIPTION"
