# Claude Code Instructions (Project Guardrails)

## Core rule
- The build is not done until `make verify` passes.

## Development style
- Prefer small commits, incremental changes, and always keep the repo runnable.
- Add/maintain tests for anything non-trivial.
- Do NOT rely on live eBird API for tests. Use fixtures in `tests/fixtures/`.

## Outputs must be deterministic
- `python -m bird_targets demo --fixtures tests/fixtures --out outputs/_demo`
  must produce outputs/ _demo/targets_ranked.csv every time.

## Completion promise
- Only output the promise tag when ALL success criteria are met:
  `<promise>PHASE_X_COMPLETE</promise>`
