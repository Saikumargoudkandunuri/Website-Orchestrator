# Checkpoint verification

Every milestone checkpoint MUST actually rerun the complete test suite and see it
pass before the checkpoint task is marked complete. No fake checkpoint completion.

## The rule

A checkpoint task (for example "Checkpoint — Core foundation", "Checkpoint —
Observe layer", "Final checkpoint — full loop") is a gate, not a formality. Before
setting a checkpoint task to complete you MUST:

1. Run the **entire** repository test suite from the repository root:

   ```
   uv run pytest
   ```

2. Observe the real result and confirm it fully passes — zero failures, zero
   errors, zero collection errors. Report the actual summary line you saw (for
   example `398 passed`).

3. Only then mark the checkpoint complete.

## What is NOT allowed

- Do not mark a checkpoint complete from memory, assumption, or "the code looks
  right." The suite must have been run in this session and observed to pass.
- Do not substitute a partial or package-by-package run for the full-suite run.
  Per-package runs (`cd packages/x && uv run pytest`) do not satisfy a checkpoint;
  the checkpoint requires the single root invocation to pass end to end.
- Do not mark a checkpoint complete while any test fails, errors, or is
  unexpectedly skipped. If tests fail, fix the root cause (or, if it is a genuine
  environment limitation, stop and raise it with the user) — never edit the gate
  to make it green.
- Do not weaken, xfail, or skip tests solely to get a checkpoint to pass.

## Environment notes

- The suite is hermetic by default: the Digital_Twin tests run against in-memory
  SQLite and require no Docker or external PostgreSQL. A single `uv run pytest`
  from the root runs the whole workspace, so "the database wasn't available" is
  not a valid reason to skip the full run.
- Optional PostgreSQL validation is opt-in only, via `WO_TEST_POSTGRES=1` (plus
  `WO_TEST_DATABASE_URL` or `DATABASE_URL`). It is never required for a checkpoint
  and must never be relied on implicitly.

## If the suite cannot be run

If you genuinely cannot run `uv run pytest` (missing toolchain, sandbox
restriction, etc.), do not mark the checkpoint complete. Say clearly that the
checkpoint is unverified and why, and ask the user how to proceed.
