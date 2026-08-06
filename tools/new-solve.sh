#!/usr/bin/env bash
# scaffold a solve directory from the template.
#   ./tools/new-solve.sh rf-replay
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
name="${1:-}"

if [[ -z "$name" ]]; then
  echo "usage: $0 <challenge-slug>" >&2
  exit 2
fi

# keep slugs boring so nothing downstream has to quote them
if [[ ! "$name" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
  echo "error: slug must be lowercase kebab-case, got '$name'" >&2
  exit 2
fi

dest="$root/solves/$name"
if [[ -e "$dest" ]]; then
  echo "error: $dest already exists, not clobbering it" >&2
  exit 1
fi

cp -r "$root/solves/_template" "$dest"
sed -i.bak "s/<challenge name>/$name/; s/<challenge>/$name/" "$dest/README.md" "$dest/solve.py"
rm -f "$dest"/*.bak
chmod +x "$dest/solve.py"

echo "$dest"
