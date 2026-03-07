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

# Configure this repository so plain `git push` to `origin` updates both
# `main` and `sample-data` together, reducing accidental branch skew.
git config --local --unset-all remote.origin.push 2>/dev/null || true
git config --local --add remote.origin.push refs/heads/main:refs/heads/main
git config --local --add remote.origin.push refs/heads/sample-data:refs/heads/sample-data

cat >"$hook_path" <<'HOOK'
#!/usr/bin/env bash
set -euo pipefail

pushes_main=0
pushes_sample_data=0
main_sha=""
sample_data_sha=""

while read -r local_ref local_sha remote_ref remote_sha; do
  [ -n "${remote_ref:-}" ] || continue
  if [ "$remote_ref" = "refs/heads/main" ]; then
    pushes_main=1
    main_sha="$local_sha"
  fi
  if [ "$remote_ref" = "refs/heads/sample-data" ]; then
    pushes_sample_data=1
    sample_data_sha="$local_sha"
  fi
done

# Block pushes that include `main` unless `sample-data` is in the same push.
if [ "$pushes_main" -eq 1 ] && [ "$pushes_sample_data" -ne 1 ]; then
  echo "pre-push: blocked because this push includes 'main' but not 'sample-data'." >&2
  echo "pre-push: push both together, for example:" >&2
  echo "  git push origin main sample-data" >&2
  exit 1
fi

# Whenever `sample-data` is pushed, require it to contain `main`.
if [ "$pushes_sample_data" -eq 1 ]; then
  if [ -z "$main_sha" ]; then
    if ! main_sha="$(git rev-parse refs/heads/main 2>/dev/null)"; then
      echo "pre-push: local branch 'main' not found; cannot verify sample-data freshness." >&2
      exit 1
    fi
  fi
  if ! git merge-base --is-ancestor "$main_sha" "$sample_data_sha"; then
    echo "pre-push: blocked because pushed 'sample-data' is not up-to-date with 'main'." >&2
    echo "pre-push: update sample-data first, for example:" >&2
    echo "  git checkout sample-data && git merge main" >&2
    echo "  # or: git checkout sample-data && git rebase main" >&2
    exit 1
  fi
fi
HOOK

chmod +x "$hook_path"
echo "Configured local push refspecs for origin: main + sample-data"
echo "Installed pre-push hook at: $hook_path"
