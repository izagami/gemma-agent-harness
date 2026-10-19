# EXPERIENCE.md — what we learned improving the 12B harness

The library of validated lessons (the "harnessing-level" memory, after Harness², Google Research 2026).
Read it before proposing a harness change; add to it after every probe or full run. Each entry names the
failure that motivated it and the evidence that it helped. Executor: Gemma 4 12B QAT, thinking off.

## Score history (45-task suite: 20 easy, 15 hard, 5 multi-file, 5 repo-scale)

| Profile | easy | hard | multi | repo | total | note |
|---|---|---|---|---|---|---|
| v6f | 20 | 14 | 4 | 0 | 39 | 30-step cap |
| v7 | 19 | 13 | 5 | 1 | 38 | 80 steps alone did not help |
| v7d | 19 | 14 | 5 | 1 | 39 | |
| v7e | 20 | 15 | 5 | 3 | 43 | run 1 |
| v7e | 20 | 13 | 5 | 2 | 40 | run 2 (2 lanes): h_sync, h_md, y_ledger_split flipped to fail -> spread ~3 tasks |
| v7e+fixes | 19 | 13 | 5 | 1 | 38 | generic fixes, soft limit 40k incl. arguments: masking started too early |
| v7e+fixes | 20 | 13 | 5 | 2 | 40 | soft limit 90k: back to v7e's level (dedupe fixed by isolated checks) |
| v7i | 19 | 13 | 5 | 1 | 38 | run 2 (todo cap in): duration = 80 todo calls (reasoning inside todo items) |
| v7i | 18 | 14 | 5 | 2 | 39 | all harness-bug fixes + plan_lock + debug rules + .agent/orig; within v7e's spread. New: todo storm (duration, context full), test run overwrote the real output (log_errors) |

## Principles (each confirmed more than once)

1. **If a program can check it, do not ask the model.** Tests failing, input files changed, a file cut off:
   every time the LLM judge was given the evidence it still accepted (v6d log_errors, v7d y_library). The
   deterministic versions (restore/read-only inputs, failing-test gate) fixed them.
2. **Loops are invisible to naive repeat detection.** The model varies something irrelevant: a `# comment`
   in a bash command (v7b y_ledger_split, 69/80 steps), a no-op edit that resets the cache (v5 h_bank, 18x),
   identical thoughts (v7e y_timesheet, 55/80 steps). Normalise before comparing; only a real file change resets.
3. **On a refused repeat, give the result, not a scolding.** Refusing without the previous output made the
   model re-run the same command 17 times (v5c import_fix).
4. **Never let a broken message into the history.** One unparsable tool call made llama-server fail every
   later request (HTTP 500 storm). Sanitise before appending.
5. **Show the model what it cannot see.** A clip that cut the middle of a file cost ~40 steps (v7e
   y_ledger_split); `read_file` line numbers were taken for file content (v6b h_access). Say exactly what was
   cut and how to get it.
6. **Test-first, checked by the harness.** A spec test written before the code and run at finish catches what
   the model's own CLI checks hide (v6c h_calc).
7. **Keep the prompt prefix stable.** Re-masking one old observation per step forced a full re-prefill each
   step (v5e). Mask rarely, in one batch.
8. **Budget alone does not fix long tasks.** 30 -> 80 steps (v7) moved repo-scale 0 -> 1 only; the extra
   steps were spent in loops until 2, 5 and the stagnation nudge were in place.

## Components and evidence

| Component (FEATURES key) | Motivating failure | Evidence |
|---|---|---|
| repeat_result | import_fix 17 re-runs | v5c 26 -> v3 level, fewer steps |
| storm | cut-off call storms, 38-70 per run | storms gone from v5d on |
| cache | prefill every step | judge 4.5 s -> fast; steps faster |
| think + think_limit | reasoning inside code comments (23 cut-offs) | v5f; limit fixed h_bank 16/30 thinks |
| spec (.agent/spec_test.py) | h_calc hidden TypeError | v6c |
| protect_inputs / judge_inputs | inputs overwritten with test data | log_errors, dedupe pass from v7d |
| hard_tests | judge accepted a broken test | y_library pass in v7e |
| read_window | middle of module clipped | y_ledger_split pass in v7e |
| semantic_repeat | comment-varied re-reads | y_ledger_split progressed in v7b |
| force_act | identical think loop | y_timesheet reached later features in v7e |
| stagnation | 12 probe variations, no edit | v7c y_library |
| v7b_rules 12-14 | retyping code, changed output, outputs from test logs | y_perf_report, log_errors |

## Neutral or rejected

- 120 steps (v7g, v7h): 1/8 and 0/8 on the four hardest tasks; loops just ran longer.
- Debugging playbook (v7i rules 15-18): y_tzreport still 0/1 (0/10 over all profiles).

- Bigger step budget without loop fixes (v7: 38/45, below v6f).
- LLM finish judge as the only check (accepted known failures several times).
- Parallel slots on one server (`-np 4`): per-slot speed fell to 3-9 tok/s; one task per server instead.
- BFCL as the target metric: did not reflect multi-step agent work.

## Open problems

- The model reasons in whatever free-text field it has: bash comments (v5), todo item texts (v7i duration, 80 todo
  calls). Text refusals are ignored; withholding the tool and length limits are the working levers.
- v7i (38, 39) is below v7e (43, 40): its additions (plan/todo refusals, rules 15-18, .agent/orig note) may hurt.
  v7e with only the generic fixes scored 38 (40k limit) and 40 (90k): the v7i additions are not clearly worse.
- Plateau: every profile from v7e on lands at 38-43. Remaining failures are y_timesheet / y_tzreport (never solved),
  and h_md / h_sync / y_ledger_split (solved about half the time). Single-run harness tweaks are now below the noise.

- Repo-scale tasks that need more than ~80 steps of real work (y_timesheet: four features from a spec;
  y_tzreport: bug in the interaction of two layers).
- Counting call arguments toward the soft limit without raising it (40k) masked file reads early in long tasks;
  repo-scale fell to 1/5. Any change to what the model sees needs a full run, not only the target task.
- Variance: v7e scored 43 and 40 on the same suite. Differences of 1-3 tasks between single full runs are noise;
  judge a change on the tasks it targets (probe, 2+ runs) and on the mean of full runs.
- Refused-repeat loops bypass the stagnation nudge (refused steps `continue` before it): v7e run 2 h_md
  (44 refused, 3 commands cycling, no edit) and y_ledger_split (48 identical writes). Targeted by v7f.

## Harness bugs found by probing (2026-10-19)

The side-by-side probes (probe.py) found more harness bugs than model weaknesses. All are fixed for every profile:
- Repeat cache reset only after write_file/edit_file: files written by bash heredocs left stale results that were
  replayed as "already ran, nothing changed" (v7h h_md: a pre-write ModuleNotFoundError replayed 60+ times; the
  model chased a non-existent import problem). Now any file change resets it. **Every earlier profile had this.**
- Context overflow at ~110 steps: write_file arguments were never masked (HTTP 400). Now counted and elided.
- Elided bash commands were copied verbatim by the model and run. Now commands keep their first 300 chars.
- read_file refused /tmp, where the rules tell the model to keep scratch copies.
- Interleaved repeat loops (never 3 in a row) and .agent/ rewrites hid stagnation from both nudges.
- todo calls were exempt from repeat checks and never elided: ~60 multi-KB todo calls filled the context (v7i duration).
  todo calls are now stored capped (12 items x 150 chars); v7f+ refuses a 3rd todo-only step in a row.

Lesson: **when the model looks stupid, first check what the harness showed it.** Read the observations in the log,
not only the actions.

## How to add an entry

After a probe (`probe.py`) or full run: the failure (task, steps, what the log shows), the change, and the
result on the failing task and on the full suite. Move an idea to Principles only after it helped twice.
