---
name: gitlab-mr-comments
description: >
  List unresolved review comments on the GitLab merge request for the current
  git branch. Use when users want to see open MR comments,
  review threads, unresolved discussions, or asks any request 
  that implies pulling open discussion items from a merge request.
---

# GitLab MR Open Comments

Fetch the list of unresolved comments on the merge request for the current git branch.

No argument needed.

`SKILL_DIR` = `{THIS_SKILL_DIRECTORY}` — the absolute path of this skill's folder.

---

## Run

```bash
bash $SKILL_DIR/scripts/list-mr-open-comments.sh
```

## Output

The script prints open MR threads in the following format.
Each thread is separated by `---`:

```
- <comment_id>
- <file_path>:<line> (or '_no file path_' for general comments)
- @<author>
  > <comment_body>
- @<reply_author>    (if replies exist)
  > <reply_body>
```


## When acting on the comments

After reading the output, treat each unresolved thread as a TODO from the reviewer.
Address the diff comments by editing the file at the indicated line; address general
comments by the context they describe. Don't resolve threads — that's the reviewer's job.
