#!/usr/bin/env bash
# Run from the old installation's host. Does not restart or change the old app.
set -euo pipefail
umask 077
root="$(cd "$(dirname "$0")/.." && pwd)"
archive="${1:?Usage: export-config.sh archive.tar.gz [running-backend-container]}"
container="${2:-}"
[[ ! -e "$archive" ]] || { echo 'Archive already exists; choose a new path.' >&2; exit 2; }
# Build a self-contained script for old containers that predate migration support.
if [[ -n "$container" ]]; then
  bundle="$(mktemp)"
  temporary="$(mktemp "$(dirname "$archive")/.monitor-export.XXXXXX")"
  trap 'rm -f "$bundle" "$temporary"' EXIT
  python3 - "$root" "$bundle" <<'PY'
from pathlib import Path
import sys
root, output = map(Path, sys.argv[1:])
config = (root / 'backend/config.py').read_text()
migration = (root / 'backend/migration.py').read_text().replace('from config import validate_config\n', '')
output.write_text(config + '\n' + migration)
PY
  if ! docker exec -i "$container" python - export --config /app/servers.yaml --secrets /run/secrets < "$bundle" > "$temporary"; then
    exit 2
  fi
  ln "$temporary" "$archive"
else
  python3 "$root/backend/migration.py" export --config "$root/servers.yaml" --secrets "$root/secrets" --output "$archive"
fi
echo "Exported to $archive. This archive contains credentials; transfer it privately."
