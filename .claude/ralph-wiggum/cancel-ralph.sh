#!/bin/bash
set -euo pipefail

# Cancel an active Ralph Wiggum loop

RALPH_STATE_FILE="${CLAUDE_PROJECT_DIR:-.}/.claude/ralph-wiggum/state.json"

if [ -f "$RALPH_STATE_FILE" ]; then
  ITERATION=$(python3 -c "import json; print(json.load(open('$RALPH_STATE_FILE')).get('current_iteration', 0))" 2>/dev/null || echo "?")
  rm -f "$RALPH_STATE_FILE"
  echo "Ralph Wiggum loop cancelled after $ITERATION iterations."
else
  echo "No active Ralph Wiggum loop to cancel."
fi
