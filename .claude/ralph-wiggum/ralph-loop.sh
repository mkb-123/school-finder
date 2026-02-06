#!/bin/bash
set -euo pipefail

# Ralph Wiggum - Start a persistent loop
# Usage: /ralph-loop "prompt" --max-iterations 50 --completion-promise "COMPLETE"

RALPH_STATE_FILE="${CLAUDE_PROJECT_DIR:-.}/.claude/ralph-wiggum/state.json"

PROMPT=""
MAX_ITERATIONS=0
COMPLETION_PROMISE="RALPH_COMPLETE"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --max-iterations)
      MAX_ITERATIONS="$2"
      shift 2
      ;;
    --completion-promise)
      COMPLETION_PROMISE="$2"
      shift 2
      ;;
    *)
      PROMPT="$1"
      shift
      ;;
  esac
done

if [ -z "$PROMPT" ]; then
  echo "Usage: /ralph-loop \"<prompt>\" [--max-iterations <n>] [--completion-promise \"<text>\"]"
  exit 1
fi

# Write state file
cat > "$RALPH_STATE_FILE" <<EOF
{
  "prompt": $(python3 -c "import json; print(json.dumps('$PROMPT'))"),
  "max_iterations": $MAX_ITERATIONS,
  "current_iteration": 0,
  "completion_promise": "$COMPLETION_PROMISE"
}
EOF

echo "Ralph Wiggum loop started."
echo "Prompt: $PROMPT"
echo "Max iterations: ${MAX_ITERATIONS:-unlimited}"
echo "Completion promise: $COMPLETION_PROMISE"
echo ""
echo "The loop will continue until you output <promise>$COMPLETION_PROMISE</promise> or hit max iterations."
echo "To cancel: /cancel-ralph"
