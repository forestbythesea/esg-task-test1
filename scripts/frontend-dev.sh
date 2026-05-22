#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
NPM_CLI="$ROOT_DIR/frontend/.local-tools/npm/bin/npm-cli.js"

if ! command -v node >/dev/null 2>&1; then
  if [ -x /Applications/Codex.app/Contents/Resources/node ]; then
    NODE_BIN=/Applications/Codex.app/Contents/Resources/node
  else
    echo "Node.js is required, but no node executable was found on PATH." >&2
    exit 1
  fi
else
  NODE_BIN=node
fi

if [ ! -f "$NPM_CLI" ]; then
  mkdir -p "$ROOT_DIR/frontend/.local-tools/npm"
  curl -L https://registry.npmjs.org/npm/-/npm-10.9.3.tgz \
    | tar -xz -C "$ROOT_DIR/frontend/.local-tools/npm" --strip-components=1
fi

if [ ! -d "$ROOT_DIR/frontend/node_modules" ]; then
  "$NODE_BIN" "$NPM_CLI" --prefix "$ROOT_DIR/frontend" install
fi

"$NODE_BIN" "$ROOT_DIR/scripts/frontend-dev.mjs"
