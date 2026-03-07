#!/usr/bin/env bash
set -euo pipefail

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "error: not inside a git repository" >&2
  exit 1
fi

git_dir="$(git rev-parse --git-dir)"
hooks_dir="$git_dir/hooks"
hook_path="$hooks_dir/pre-push"

mkdir -p "$hooks_dir"

cat >"$hook_path" <<'HOOK'
#!/usr/bin/env bash
set -euo pipefail

if ! git show-ref --verify --quiet refs/heads/main; then
  echo "pre-push: local branch 'main' not found; cannot verify sample-data freshness." >&2
  exit 1
fi

if ! git show-ref --verify --quiet refs/heads/sample-data; then
  echo "pre-push: local branch 'sample-data' not found; cannot verify freshness vs main." >&2
  exit 1
fi

if ! git merge-base --is-ancestor refs/heads/main refs/heads/sample-data; then
  echo "pre-push: blocked because 'sample-data' is behind 'main'." >&2
  echo "pre-push: update it first, for example:" >&2
  echo "  git checkout sample-data && git merge main" >&2
  echo "  # or: git checkout sample-data && git rebase main" >&2
  exit 1
fi
HOOK

chmod +x "$hook_path"
echo "Installed pre-push hook at: $hook_path"
