#!/bin/bash

set -u

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  echo "Usage: create-mr.sh [--help] [-- <extra glab args>...]"
  echo ""
  echo "Creates a GitLab merge request from the current branch."
  echo "Title and description are auto-filled, and the"
  echo "branch is pushed automatically. The target branch is the project default."
  echo ""
  echo "Options:"
  echo "  --help, -h         Show this help message"
  echo "  <extra glab args>  Any additional arguments are forwarded to 'glab mr create'"
  echo "                     (e.g. --target-branch develop --label backend --draft)"
  echo ""
  echo "Requirements:"
  echo "  - glab CLI installed and authenticated: https://docs.gitlab.com/cli/"
  echo "  - At least one commit on the current branch"
  exit 0
fi

if ! command -v glab >/dev/null 2>&1; then
  echo "Failed to create MR: 'glab' CLI is not installed."
  echo "glab: https://docs.gitlab.com/cli/"
  echo "Surface this to the user clearly — don't try to work around it."
  exit 1
fi

strip_ansi() {
  sed $'s/\033\[[0-9;]*m//g'
}

CREATE_OUTPUT=$(glab mr create --description " " --fill --yes "$@" 2>&1)
CREATE_STATUS=$?

CREATE_OUTPUT=$(echo "$CREATE_OUTPUT" | strip_ansi)

if [ $CREATE_STATUS -ne 0 ]; then
  # An MR may already exist for this branch — that's not an error, just surface it.
  if echo "$CREATE_OUTPUT" | grep -qi "already exist"; then
    echo "$CREATE_OUTPUT"
    echo "An MR already exists for this branch — surface this to the user as-is."
    exit 0
  fi
  echo "Failed to create MR:"
  echo "$CREATE_OUTPUT"
  exit 1
fi

echo "$CREATE_OUTPUT"
