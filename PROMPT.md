You are Claude Code running inside my repository.

PHASE A GOAL
Implement a minimal, testable “data spine” that produces a ranked list of under-reported species using OFFLINE fixtures.

STRICT SUCCESS CRITERIA (all must pass)
1) `make verify` passes locally with NO network required.
2) `python -m bird_targets demo --fixtures tests/fixtures --out outputs/_demo` creates:
   - outputs/_demo/targets_ranked.csv
3) Repo includes:
   - src/bird_targets/ (package)
   - src/bird_targets/__main__.py (CLI entry)
   - src/bird_targets/ebird_client.py (real client wrapper, but tests must not call network)
   - src/bird_targets/cache.py (SQLite cache)
   - src/bird_targets/scoring.py (Durham vs adjacent scoring using fixtures)
   - tests/ covering scoring + CLI demo path

FUNCTIONAL REQUIREMENTS
- Implement region discovery in code, but for demo/tests use fixture `regions.json`.
- Implement “under-reported score” v0:
  - Expected presence: species common in adjacent fixtures but rare/absent in Durham fixtures.
  - Output columns at minimum:
    species_code, common_name, expected_score, observed_score, underreported_score
- Implement exclusions via config (even if simple v0 list): vagrants/pelagic/flyovers/exotics excluded.

DEVELOPER REQUIREMENTS
- Add/update CLAUDE.md guardrails.
- Keep changes incremental.
- If any dependency missing, add it to requirements.txt.

WORKFLOW
- Run tests/lint frequently.
- Fix failures.
- Do not output the promise until ALL success criteria pass.

WHEN DONE
Print exactly: <promise>PHASE_A_COMPLETE</promise>
