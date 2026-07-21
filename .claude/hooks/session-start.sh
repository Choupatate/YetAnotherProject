#!/bin/bash
# Sets up the Python virtualenv for Storybook (see CLAUDE.md "Running it")
# so pytest/ruff/python are ready to go in Claude Code on the web sessions.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

# requirements.txt pins both runtime deps (flask, pillow, ...) and the dev
# tools (pytest, ruff) used by CI, so one install covers everything.
.venv/bin/pip install -q -r requirements.txt

# Make python/pytest/ruff resolve to the venv without needing `.venv/bin/`
# prefixes or `source .venv/bin/activate` in every command.
echo "export PATH=\"$CLAUDE_PROJECT_DIR/.venv/bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"
