#!/usr/bin/env bash
set -euo pipefail

PROMPT_FILE="${1:-PROMPT.md}"

# Ralph: repeat until Claude prints the completion promise and verify passes.
while :; do
  echo "=== RALPH ITERATION $(date) ==="
  cat "$PROMPT_FILE" | claude-code

  # If Claude claims done, enforce the verifier.
  if grep -q "<promise>PHASE_A_COMPLETE</promise>" "$PROMPT_FILE" 2>/dev/null; then
    echo "Note: promise is in prompt file; this script expects Claude to print it in output."
  fi

  if make verify; then
    echo "Verifier passed."
  else
    echo "Verifier failed. Looping..."
    continue
  fi

  echo "If Claude printed the promise and make verify passed, you can stop the loop."
done
