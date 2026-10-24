# Lessons v8: procedural knowledge mined from agent trajectories

Source: all of `runs/` as of 2026-10-21. There are 1767 results; 1528 passed and 239 failed, 14 of the failures CAD and 10 errors. Among the 225 non-CAD failures:

- **59% hit the step cap** (133 runs). Most of these were loops.
- **34% called finish with a wrong result** that the harness accepted (77 runs).
- **v7-era runs** (v7, v7d, v7e, v7i): 82 of 130 failures (63%) never called finish. The v7e finish gates (spec_test, project tests, judge) therefore never ran for them.

**Method.** 157 failed trajectories with logs were classified one by one, and about 43 passed runs of the same tasks were read for contrast. The tasks covered: h_md, h_sync, y_timesheet, y_tzreport, y_ledger_split, y_library, y_perf_report, log_errors, duration, h_calc, h_bank, h_ini, dedupe, h_dupes, stats_cli, h_access, and every small task that has a failed log. The fixed process taxonomy below assigns one primary cause per run; one run was counted twice, so the total is 158. The models were mostly Gemma 4 12B (all 10-18 and 10-19 runs), plus 10-21 comparison runs with larger models. Older profiles (v0-v6) account for most THRASH, TOOLCALL_DEGEN and INPUT_CLOBBER failures on small tasks. The repo-scale y_* tasks are almost all v7-era.

**What v7e already tells the agent.** The system prompt asks it to:
- Start with a todo checklist and explore first.
- Make precise edits and verify every requirement with a command.
- Keep the exact names and formats, and not modify tests.
- Use the think tool, with short thoughts.
- Never overwrite inputs (put test data in /tmp).
- Fix noticed problems.
- Write `.agent/spec_test.py` first.
- Copy code by line range.
- Save `.agent/before.txt` and diff against it.
- Re-run the program on the real inputs and cat the outputs.

**What v7e enforces mechanically:**
- a py_compile check with rollback on every edit;
- compileall at finish;
- finish is rejected while the project's tests fail (up to 4 times);
- finish is rejected while spec_test is missing or failing;
- inputs modified without permission are restored, judged per file;
- repeated calls are refused and the earlier result is replayed, with semantic repeat detection;
- a stagnation nudge after 10 steps with no file change while a check fails;
- the think tool is withdrawn after 2 consecutive thinks;
- an LLM judge at finish.

The lessons below try not to restate these. They target what the rules and gates did not prevent.

## (a) Failure taxonomy

| category | primary count | what it means | examples |
|---|---|---|---|
| **THRASH** Thrashing / no progress | 36 | loops of probes, re-reads or identical rewrites until the step cap | y_tzreport v7d-1019-014200: named the bug, made zero code edits, wrote /tmp/debug_store_v3..v33.py until step 80<br>y_timesheet v7d-1019-014200: wrote 'I will now implement [alias]' ~20 times in think calls without acting |
| **REQ_MISS** Skipped or misread requirement | 19 | an explicit rule (often a 'do not' rule, or one in a docstring/comment) never implemented or checked | h_sync (11 runs): printed a line type the task explicitly says not to print; it was visible in the agent's own output and never compared to the rule<br>y_library v7-1019-004944: test file not discoverable by the required runner (0 tests found), never counted after the last write |
| **EDGE** Only simple cases tested | 14 | missed interaction/adjacency/look-alike cases the spec implies | h_md v7e-1021-125025: 21-case spec_test used one construct per input; two blocks adjacent without a blank line never tested; finished at step 11 of 80<br>h_sync (several): change detection tested only with data of different lengths, so a look-alike change was missed |
| **TOOLCALL_DEGEN** Oversized or malformed tool calls | 13 | huge write_file/think/todo arguments that fail JSON parsing, todo storms | duration (6 runs): todo storms / giant invalid-JSON write_file, the target file never written<br>h_ini v3/v5/v0: one ~16k-char write_file with broken JSON resent until the cap |
| **BROKE** Broke existing behaviour | 12 | regression of existing tests/API/output | y_timesheet v7i-1019-121425: whole-file rewrite of a module dropped a function the existing tests import; tests never re-run<br>y_library v7d-1019-014200: routing change broke an existing test, called it 'strange', finished |
| **SPEC_WRONG** Own test encoded a misreading | 11 | spec_test guessed expectations, was edited to match the code, or compared new code with itself | y_perf_report v7-1018-230856: regenerated the 'expected' baseline with the modified program each time, so diff was always empty<br>log_errors v7e-1020-064925: edited a correct spec_test to accept its own wrong output format |
| **INPUT_CLOBBER** Real inputs/outputs overwritten | 11 | test data written into the task's input/output files or tests; cleanup deleted the real output | dedupe v7e-1019-150747: spec_test cleanup deleted the real output file when the harness re-ran it at finish<br>log_errors v7d-1019-014200: a test run overwrote the real report with test counts |
| **EDIT_MECH** Edit mechanics / destroyed source | 11 | retyped code from memory, whole-file rewrite dropped names, missing path, source deleted before the move | y_ledger_split v7e-1019-150747: rm'd the source module before the new module existed, then retyped it from memory with a syntax error<br>y_timesheet v7e-1021-041500: put one module's content into another file, lost the original with no backup, spent 35 steps rebuilding |
| **STUCK_APPROACH** Kept a failing approach | 8 | same fix/hypothesis re-tried; unverified belief never checked | y_tzreport v7e-1021-062607: acted on an unchecked belief about a datetime method for ~30 near-identical probes<br>h_ini v5c-1018-154109: eight whole-file rewrites with no test run between them |
| **HARNESS_INFRA** Infrastructure | 6 | HTTP 500, context overflow, container lost (not a process failure) | y_timesheet v7e-1020-093355: HTTP 500 at step 36<br>y_ledger_split v7e-1021-041503: 32k context filled |
| **SHELL_QUOTING** Shell-mangled probe input | 5 | backticks/$ inside python3 -c "..." were executed by bash; agent debugged corrupted output | h_md v7e-1019-065150: test string with backticks inside python3 -c "..."; bash ran it as a command; 44 refused repeats chasing a phantom regex bug |
| **OUTPUT_FMT** Output format drift | 5 | field order, prefixes, extra attributes, separators differ from the task | h_md v5c/v6: added an attribute to a required HTML tag<br>log_errors v6-1018-152414: wrong field order and an extra folder prefix |
| **DATA_MISREAD** Misread data display | 3 | counted by eye; took read_file line-number prefixes or cat -A markers as content | h_access (4 runs): counted bad lines from the read_file/cat -A display and got 2 instead of 1 |
| **PREMATURE** Finished despite visible failure | 2 | own output showed a traceback / over-limit time, finished anyway | h_calc v5-1018-134012: own probe printed a traceback on a valid case; finished anyway<br>h_dupes v5b: finished with a measured 16 s against a 2 s limit |
| **EXPLORE** Wrote before reading | 1 | tests/code written before reading the wiring and existing tests (secondary in 3 more) | y_library v7e-1021-041500: wrote tests at step 8 before reading router/main/handlers; they assumed a wrong storage API; 40 steps fixing own tests |
| **PATHS** cwd / path assumptions | 1 | output path relative to cwd; spec_test import needing PYTHONPATH (secondary in >=14 runs) | fizzbuzz v7e-1021-125025: wrote its output relative to cwd; grader ran from another dir<br>h_md/h_calc/dedupe/perf (>=14 runs): spec_test imported the project only via `export PYTHONPATH=.`; harness run from .agent/ failed 'No module named' |
| total | 158 | | |

**Frequent secondary causes.** These co-occur with the primary cause, and several are just as important:

- **spec_test cannot import the project (PATHS):** at least 14 runs, passes included. The harness runs `python3 .agent/spec_test.py` in isolation, so only `.agent/` is on sys.path. Models that relied on `export PYTHONPATH=.` failed the gate, blamed the harness and lost 3-6 steps. In h_md the gate auto-accepted on the third try.
- **Existing tests failing in the final state:** 10 of 28 y_timesheet/y_tzreport failures. Almost always a whole-file rewrite dropped a public name. These runs never reached finish, so the tests gate never fired.
- **Own test was wrong (SPEC_WRONG):** about 12 runs as a secondary cause. Patterns: changing the code to match a wrong own test, editing a correct test to match wrong output, and baselines regenerated after edits (3 y_perf_report runs: diff against itself).
- **Named the cause but made no edit (NO_ACT, part of THRASH):** 5 y_tzreport runs.
- **No final run (NOFINALRUN):** about 8 runs. Also scratch files and configs left in the repo (2), and an imported API name that does not exist (1).
- **Malformed tool calls:** write_file without a path, or invalid JSON in large arguments. Seen in most Gemma long runs, costing 1-20 steps each. Whole-file writes over about 1.5k characters failed most often.
- **Not reproducing the bug (NOREPRO) was rare.** Every y_tzreport run ran the failing tests within the first 5 steps. The weakness is acting on the reproduction, not producing it.

## (a2) Bare vs harnessed: what the models lack with no harness at all

**Runs compared.**

- **Bare (v0):** `runs/v0-1018-114024` (20 easy tasks, eval-run1.out) and `runs/v0-1018-121943` (15 hard tasks, eval-run2.out). This is `agent.py` with V0_SYSTEM: a 2-line prompt, tools bash/read_file/write_file/edit_file/finish, 30 steps, and no other features. There is no nudge, no repeat guard and no broken-call recovery; a text reply ends the run.
- **Prompt-only (v1):** `runs/v1-1018-115458`. This adds the 6-rule V1 prompt, nudge, a verify-before-finish message and a repeat warning.
- **Harnessed:** v3-v7e, all on `agent.py`/`agent_v5.py` with their features.
- **Model and suite:** all bare runs are Gemma 4 12B (2026-10-18). The bare suite had no multi-file or repo-scale tasks.

The comparison below uses the 35 tasks that both bare and harnessed runs share.

| profile | failures on the 35 shared tasks |
|---|---|
| v0 bare | 8 / 35 (22.9%) |
| v1 prompt only | 5 / 20 (25.0%) |
| v3-v6 | 69 / 506 (13.6%) |
| v7e | 24 / 595 (4.0%) |

**Primary causes, bare plus prompt-only (13 failures) vs harnessed (v3-v7, 145 failures):**

| category | bare + v1 | harnessed | status under v7e |
|---|---|---|---|
| THRASH (exact repeats) | 4 (31%) | 32 (22%) | Exact repeats are **fixed mechanically**: they are refused and the earlier result is replayed, with semantic repeat detection, a stagnation nudge and force_act. What remains is varied loops: renamed debug scripts, think-without-act, re-reading clipped files. |
| TOOLCALL_DEGEN | 4 (31%) | 9 (6%) | **Mostly fixed.** Broken calls are sanitised and no longer crash the run, storm protection was added, and the think tool takes reasoning out of code. In bare v0, 3 of 35 runs were killed outright by one invalid or oversized call (HTTP 500). Large write_file calls still fail often in v7 logs, at a cost of steps rather than the run. |
| EDIT_MECH | 2 | 9 | **Partly fixed.** Whitespace-tolerant matching, the compile check with rollback and line-number hints help. Bare/v1 copied read_file line prefixes into old_text (config_edit, robust: about 20 retries each) and applied the same no-op edit 10 times (h_bank). Whole-file rewrites that drop names remain. |
| SHELL_QUOTING | 1 | 4 | **Not fixed.** |
| OUTPUT_FMT | 1 | 4 | **Not fixed.** |
| EDGE | 1 | 13 | **Not fixed.** |
| REQ_MISS | 0 | 19 | **Not fixed**; mostly on harder tasks. |
| BROKE | 0 | 12 | **Not fixed.** The tests gate catches it only if the agent calls finish, and 63% of v7 failures never did. |
| SPEC_WRONG | 0 | 11 | **Created by the harness.** Bare models rarely write tests, so their tests cannot be wrong. |
| INPUT_CLOBBER | 0 | 11 | **Partly fixed** by restore_inputs. The remaining cases come from spec_test side effects when the harness re-runs it at finish. |
| PATHS (spec_test import) | 0 | 1 (+14 secondary) | **Created by the harness**: the isolated `python3 .agent/spec_test.py` run. |
| STUCK, DATA_MISREAD, PREMATURE, EXPLORE, INFRA | 0 | 20 | Not fixed; mostly hard or repo tasks that bare runs did not attempt. |

**Behaviour of all 35 bare runs.** These numbers include the passes, and show deficits that the easy tasks hid:

- **Repeats:** 37% of bare runs, passes and fails alike, made 3 identical calls in a row. v7 passes did so 9% of the time. Without a guard, a small model re-sends the same command or edit until the steps run out: h_dupes ran the same micro-benchmark about 20 times, csv_sum repeated a rewrite and cat -A loop, h_bank repeated an edit 10 times.
- **No check after the last write:** only 59% of bare passes ran anything after their last write. 3 of 27 passes never ran the program at all and passed by luck.
- **Little testing:** only 29% of bare passes wrote or ran any test or assert, against 99% for v7 passes, where the harness prompts for it.
- **No stopping:** 12 of 27 bare passes never called finish. The output was already correct, but the model kept going until the 30-step cap, so it has no stopping criterion.
- **No exploration problem:** 96% of bare passes began by exploring (ls/cat/read_file). The model does this unprompted.

**Conclusions for the lessons and playbooks:**

- **What a bare model lacks first:**
  - not repeating itself (L01, L20);
  - keeping tool calls small (L19);
  - editing mechanics (L30);
  - running something after the last change (L16, checklist);
  - knowing when to stop (L29).
  The harness covers these mechanically.
- **What remains with the harness:** requirement coverage (L04, L05), interaction cases (L06), keeping its own tests honest (L07, L08), protecting existing behaviour during edits (L09-L13), and acting rather than probing (L01, L02, L21, L22).
- **What the harness introduces:** spec_test import and side effects (L14, L15). Bare playbooks therefore keep tests in /tmp. The harness playbooks use `.agent/spec_test.py` with an explicit `sys.path.insert(0, '/work')`.
- **Small sample.** The bare sample is small (8 bare + 5 prompt-only failures), so treat its percentages as indicative. The per-run behaviour numbers (35 runs) are firmer than the failure counts.

## (b) What passing runs did differently

These are same-task contrasts: what the passing runs did that the failing runs of the same task did not.

- **Read everything first, in a few batched commands.** The y_library, y_tzreport and y_timesheet passes read the entry point, the wiring, every touched module and the existing tests in 3-4 steps, before writing anything. The y_library failure that wrote tests at step 8 got the storage API wrong and spent 40 steps fixing its own tests.
- **Ran the existing tests after every module change,** not only at the end. The y_timesheet pass did this; 8 of 16 y_timesheet failures ended with existing tests broken and never re-ran them. y_ledger_split passes ran unittest up to 22 times.
- **Wrote one test per spec rule, named after the rule.** The h_sync pass had a case for each rule: one for every sentence, including each "do not print X" sentence. The failures tested the main flow only, so explicit "do not" rules went unchecked, even though the violation was visible in their own output.
- **Decided disagreements from the spec.**
  - Passes: when their own test failed, they re-read the spec or worked out the value by hand. The h_calc pass found its own test said 22 where the correct value was 26, and fixed the test. The y_library pass hit "date is not callable" and fixed its test to match the documented interface.
  - Failures: they changed whichever side was easier. y_library v7e-1019-150747 changed the code's interface to fit its test.
- **Edited soon after naming the cause.** The y_tzreport passes confirmed each hypothesis with one short script, then fixed one bug per edit where the state lives, and re-ran the tests after each edit. 5 of the 12 failures named the right cause and then made no edits for 50+ steps.
- **Froze a real baseline.** The y_perf_report passes kept the original package in /tmp/orig and compared byte for byte on several seeds. The failures compared new code with itself, or regenerated "before.txt" after editing. All 6 passes used diff or cmp; none of the 3 failures with wrong output did.
- **Kept tests side-effect free.** The log_errors pass built fixtures in a temp dir behind a configurable path, then re-ran on the real logs and checked that the report held no test rows. The failures wrote fixtures into the real input dir or the real output, and the harness's finish-time re-run of spec_test then clobbered the correct output.
- **Made spec_test self-contained.** The fast passes (h_md 1021, duration v7e) put `sys.path.insert(0, "/work")` in the test, so the finish gate passed on the first try.
- **Probed safely.** The h_md passes fed test input via `printf '...' |` in single quotes or a heredoc. The h_md failures put backticks inside `python3 -c "..."` and debugged bash's command substitution for dozens of steps.
- **Ran it like the grader.** The y_timesheet pass checked v1 behaviour and the examples from a /tmp cwd with PYTHONPATH=/work. The h_sync pass checked the DST tree after the real run, then ran a second time and tried an empty source.
- **Stopped when done.** The passes called finish once everything was green. y_library v7e-1021-043545 was fully green at step 52, kept working, and at step 70 rewrote a module with a non-existent import.

## (c) Generalized lessons

Task-agnostic, imperative, one line each. Counts are primary-cause counts out of 158 classified failures; several lessons also target frequent secondary causes noted above.

| id | lesson | addresses (primary count) | task types |
|---|---|---|---|
| L01 | After two probes give the same result, stop probing: edit the code or change the hypothesis. | THRASH (36), STUCK_APPROACH (8) | bugfix, investigate, feature |
| L02 | As soon as you can name the cause, make the edit in the next step; do not re-confirm it with more debug scripts. | THRASH (36) | bugfix, investigate |
| L03 | For a long spec, finish one subsection completely (code, its asserts, existing tests green) before starting the next. | THRASH (36), REQ_MISS (19), BROKE (12) | feature |
| L04 | Write one named assert per sentence of the task, including every 'do not', 'only one', 'keep X' rule and rules stated in docstrings, comments or docs. | REQ_MISS (19), SPEC_WRONG (11) | feature, scratch, bugfix, refactor |
| L05 | Passing the visible tests is not done: check each written requirement the tests do not cover with its own command. | REQ_MISS (19), PREMATURE (2) | bugfix, investigate, feature |
| L06 | Test interactions, not just single features: constructs adjacent with no separator, nested items, duplicates, empty input, values that differ but look alike, repeated and reordered calls. | EDGE (14) | scratch, feature, bugfix |
| L07 | Take expected values only from the task text or from running the original code, never from the code you are writing. | SPEC_WRONG (11) | scratch, feature, refactor, bugfix |
| L08 | When your test and your code disagree, quote the task line that decides it before changing either; never edit a test or its data just to make it pass. | SPEC_WRONG (11), STUCK_APPROACH (8) | scratch, feature, refactor, bugfix |
| L09 | Run the existing test suite after every edit to an existing module, not only before finish; a newly failing existing test means your change is wrong. | BROKE (12), EDIT_MECH (11) | bugfix, feature, refactor |
| L10 | Change existing files with small edit_file edits; before any unavoidable whole-file rewrite, cp the file to /tmp/<name>.orig and afterwards check every def/class it had still exists. | BROKE (12), EDIT_MECH (11), THRASH (36) | bugfix, feature, refactor |
| L11 | Copy code by line range (sed -n 'A,Bp' or Python slicing), never retype it, and delete the old code only after the new location imports and passes the tests. | EDIT_MECH (11), BROKE (12) | refactor |
| L12 | For 'behaviour must not change': copy the original code to /tmp/orig and save its output once before the first edit; never regenerate the baseline; diff after every change on several inputs. | BROKE (12), SPEC_WRONG (11) | refactor |
| L13 | When you swap an algorithm or data structure, keep the original's order, tie and duplicate rules; test with inputs that contain duplicates and ties. | BROKE (12) | refactor |
| L14 | Put `import sys; sys.path.insert(0, '/work')` at the top of .agent/spec_test.py; the harness runs it without your PYTHONPATH or cd. | PATHS (1), THRASH (36) | scratch, feature, bugfix, refactor, investigate |
| L15 | Make spec_test side-effect free: build fixtures in tempfile.mkdtemp(), never write to, regenerate or delete the task's real input, output or test files; the harness re-runs it at finish. | INPUT_CLOBBER (11) | scratch, feature, investigate |
| L16 | Keep test data and scratch files in /tmp; as the last action run the program on the real inputs and cat the real output. | INPUT_CLOBBER (11), OUTPUT_FMT (5) | scratch, investigate, feature |
| L17 | Run the program exactly the way the task says it is graded (other cwd, PYTHONPATH, python3 -m pkg); resolve file paths from argv or the script's location, not the cwd. | PATHS (1) | scratch, feature |
| L18 | Put test input that contains backticks, $ or quotes in a file or a quoted heredoc (<<'EOF'), never inside python3 -c "..."; 'command not found' in stderr means the probe was corrupted. | SHELL_QUOTING (5), THRASH (36) | scratch, feature, bugfix |
| L19 | Keep each tool call small: write files longer than about 80 lines in parts (write, then mode=append), keep todo items to a few words, keep reasoning short. | TOOLCALL_DEGEN (13) | scratch, feature, refactor, bugfix, investigate |
| L20 | After a tool call fails, change the method (smaller call, edit_file, heredoc), not resend it, then ls the exact file name to confirm it exists. | EDIT_MECH (11), TOOLCALL_DEGEN (13), THRASH (36) | scratch, feature, refactor, bugfix, investigate |
| L21 | If the same fix fails twice, re-read the relevant source and the task from the top and pick a different approach. | STUCK_APPROACH (8), THRASH (36) | bugfix, investigate, refactor |
| L22 | Check every belief about a library, an API name or a hand-computed number with a one-line python3 -c before acting on it; import only names you have seen in the code. | STUCK_APPROACH (8), THRASH (36) | bugfix, investigate, feature |
| L23 | Before editing a multi-module project, read the entry point, the wiring (main, router, __init__), the modules you will touch and the existing tests, batched in a few commands. | EXPLORE (1), BROKE (12) | bugfix, feature, refactor, investigate |
| L24 | Fix a bug where the bad value or state is produced, not in one of its callers; then test the requirement from the caller's side. | REQ_MISS (19), STUCK_APPROACH (8) | bugfix, investigate |
| L25 | Compare your output with the task's format character by character (field order, separators, prefixes, rounding, exact tags); print with repr() when whitespace matters. | OUTPUT_FMT (5), REQ_MISS (19) | scratch, feature, investigate |
| L26 | Count and measure with code (wc -l, len(), a script), never by eye; read_file line numbers and cat -A markers are not file content. | DATA_MISREAD (3) | investigate, scratch |
| L27 | Treat any traceback, non-zero exit or over-limit number in your own output as a failure to fix, and test the real function, not a wrapper that catches exceptions. | PREMATURE (2), EDGE (14) | scratch, bugfix, feature |
| L28 | When a task changes files or state, check the resulting state (ls -R, diff -r, cat) for every mode, and run it twice to see that the second run changes nothing. | EDGE (14), REQ_MISS (19) | scratch, feature |
| L29 | Once every requirement is checked green, call finish; do not rewrite working files late in the run or spend the remaining steps re-checking. | BROKE (12), THRASH (36) | feature, bugfix, refactor, scratch |
| L30 | Copy edit_file old_text from the file without read_file's line-number prefixes, and re-read the changed lines once to confirm the edit really changed something. | EDIT_MECH (11), THRASH (36) | bugfix, feature, refactor |
