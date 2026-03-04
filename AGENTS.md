# Agent Notes

- Keep temporary/debug files inside `.tmp/` (repo-local), not `/tmp`.
- Reason: using `.tmp/` avoids sandbox/escalation prompts and keeps scratch artifacts in the workspace.
- Agent may create commits proactively when changes are coherent and useful.
- If commit strategy needs special handling (squash/split/message format), user will specify.
