# Agent Notes

- Keep temporary/debug files inside `.tmp/` (repo-local), not `/tmp`.
- Reason: using `.tmp/` avoids sandbox/escalation prompts and keeps scratch artifacts in the workspace.
- Agent SHOULD proactively and frequently create commits when appropriate (especially after coherent, validated progress).
- If a change is a minor tweak to the immediately previous change, amend the previous commit instead of creating a new commit.
- When amending, update the commit message if needed so it accurately reflects the revised scope.
- If commit strategy needs special handling (squash/split/message format), user will specify.
