#!/bin/bash
set -euo pipefail

# Ralph Wiggum Stop Hook
# Blocks Claude from exiting and re-feeds the prompt to create a persistent loop.
# The loop continues until:
#   1. The completion promise is found in the transcript
#   2. Max iterations are reached
#   3. The loop is cancelled via /cancel-ralph

RALPH_STATE_FILE="${CLAUDE_PROJECT_DIR:-.}/.claude/ralph-wiggum/state.json"

# If no active ralph loop, allow normal exit
if [ ! -f "$RALPH_STATE_FILE" ]; then
  exit 0
fi

# Read state
PROMPT=$(python3 -c "import json; print(json.load(open('$RALPH_STATE_FILE'))['prompt'])" 2>/dev/null || echo "")
MAX_ITERATIONS=$(python3 -c "import json; print(json.load(open('$RALPH_STATE_FILE')).get('max_iterations', 0))" 2>/dev/null || echo "0")
CURRENT_ITERATION=$(python3 -c "import json; print(json.load(open('$RALPH_STATE_FILE')).get('current_iteration', 0))" 2>/dev/null || echo "0")
COMPLETION_PROMISE=$(python3 -c "import json; print(json.load(open('$RALPH_STATE_FILE')).get('completion_promise', 'RALPH_COMPLETE'))" 2>/dev/null || echo "RALPH_COMPLETE")

# If no prompt, allow exit
if [ -z "$PROMPT" ]; then
  exit 0
fi

# Check if completion promise was output in the transcript
if [ -n "${TRANSCRIPT_PATH:-}" ] && [ -f "$TRANSCRIPT_PATH" ]; then
  if grep -q "$COMPLETION_PROMISE" "$TRANSCRIPT_PATH" 2>/dev/null; then
    echo "Ralph Wiggum: Completion promise found. Loop complete after $CURRENT_ITERATION iterations." >&2
    rm -f "$RALPH_STATE_FILE"
    exit 0
  fi
fi

# Check max iterations
NEXT_ITERATION=$((CURRENT_ITERATION + 1))
if [ "$MAX_ITERATIONS" -gt 0 ] && [ "$NEXT_ITERATION" -gt "$MAX_ITERATIONS" ]; then
  echo "Ralph Wiggum: Max iterations ($MAX_ITERATIONS) reached. Stopping loop." >&2
  rm -f "$RALPH_STATE_FILE"
  exit 0
fi

# Update iteration count
python3 -c "
import json
with open('$RALPH_STATE_FILE', 'r') as f:
    state = json.load(f)
state['current_iteration'] = $NEXT_ITERATION
with open('$RALPH_STATE_FILE', 'w') as f:
    json.dump(state, f, indent=2)
"

# Block exit and re-feed prompt (exit code 2 = block exit)
echo "Ralph Wiggum: Iteration $NEXT_ITERATION - re-feeding prompt..." >&2
cat <<EOF
{"decision": "block", "reason": "Ralph Wiggum loop iteration $NEXT_ITERATION of ${MAX_ITERATIONS:-unlimited}", "message": "Continue working on the following task. This is iteration $NEXT_ITERATION. When you are fully done, output <promise>$COMPLETION_PROMISE</promise>.\n\nTask: $PROMPT"}
EOF
