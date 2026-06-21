#!/usr/bin/env zsh
set -euo pipefail

PORT="${1:-4096}"
HOST="127.0.0.1"

# Keep the server bound to localhost. If you intentionally expose it beyond
# localhost, set OPENCODE_SERVER_PASSWORD first and review the risk.
if [[ -z "${OPENCODE_SERVER_PASSWORD:-}" ]]; then
  echo "Warning: OPENCODE_SERVER_PASSWORD is not set. Use localhost only unless a password is configured." >&2
fi

opencode serve --hostname "$HOST" --port "$PORT"
