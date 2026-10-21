---
name: gitlab-mr-create
description: >
  Create a GitLab merge request from the current git branch. Use when users 
  want to open or create an MR (merge request).
argument-hint: "[isDraft]"
---

# GitLab Create MR

Create a merge request for the current git branch.

`SKILL_DIR` = `{THIS_SKILL_DIRECTORY}` — the absolute path of this skill's folder.

## Arguments

- `isDraft` (optional, default `false`) — is MR should be created as a draft, when `true`
  pass `--draft` to script call

---

## Run

```bash
bash $SKILL_DIR/scripts/create-mr.sh
```

## Output

Create mr result.

## Notes

- Title and description are auto-filled.
- The branch is pushed automatically before the MR is created.
- The target branch is the project's default branch.

If the user wants a custom title or a different target branch, that's outside
this skill — handle it with `glab mr create` flags directly.
