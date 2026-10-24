# Playbooks v8 (procedural memory for small coding agents)

Derived from 157 failed and ~43 passed trajectories in runs/ (see lessons-v8.md). Each step addresses an observed failure. 'Harness already does' lists what v7e enforces mechanically, so the playbook does not spend steps on it. Key fact: v7e's gates (spec_test, project tests, compile, judge) run only when the agent calls finish; 82 of 130 v7-era failures (63%) never called finish, so per-edit checks have to come from the agent itself.

## bugfix: Bug fix in an existing codebase

```
1. Read the entry point, the modules on the failing path and the existing tests in 2-4 batched commands (cat a b c).
2. Run the failing test or command once and save the output: ... > /tmp/before.txt 2>&1.
3. Write the smallest reproduction (one or two records) in /tmp/repro.py; work out the correct result from the task text.
4. Name the cause in one short think, then edit in the NEXT step with edit_file. No more debug scripts first.
5. Fix where the bad value is produced, not in a caller. Expect more than one bug.
6. After each edit: run /tmp/repro.py and the full existing test suite. A newly failing old test means your edit is wrong.
7. Same result after two probes, or same fix failing twice: re-read the source and pick another hypothesis.
8. Check beliefs about libraries or numbers with one python3 -c line before relying on them.
9. Tests green is not done: add one assert per task requirement the tests do not cover (repeat calls, mutation, order).
Harness already does: compile check on every edit, project tests gate at finish, spec_test gate at finish. It does NOT run tests between edits - you must.
```

## feature: Feature addition with a long spec

```
1. Read the spec, the entry point, the wiring (main/router/__init__), the modules to change and the existing tests. Run the existing tests once.
2. todo: one short item per spec subsection (a few words each).
3. Work one subsection at a time: asserts for it in .agent/spec_test.py, then the code, then spec_test + existing tests. Next subsection only when green.
4. Asserts: one per spec sentence, including 'do not', 'only', 'keep' rules and examples; expected values from the spec, never from your output.
5. Add interaction asserts: features combined, items adjacent, empty input, overrides and precedence.
6. Change existing modules with edit_file. Before a whole-file rewrite: cp f /tmp/f.orig, then check every def/class is still there.
7. If your assert fails, quote the spec line before changing code or assert. Never edit an assert to match the output.
8. Run the CLI the way it is graded: cd /tmp && PYTHONPATH=/work python3 -m pkg ...; compare with the spec character by character.
9. Re-check that the old behaviour (existing commands, error messages, exit codes) is unchanged.
Harness already does: todo prompt, spec_test must exist and pass at finish, existing tests gate at finish, compile check. These fire only at finish; most failed runs never got there.
```

## refactor: Refactor / migration preserving behaviour

```
1. Read all modules, scripts and tests involved. Run the tests and every script once.
2. Freeze the baseline ONCE: cp -r the package to /tmp/orig; save outputs to .agent/before_*.txt. Never regenerate them later.
3. Make baselines for new inputs by running /tmp/orig, never the code you are changing.
4. Move code by line range: sed -n 'A,Bp' old.py >> new.py (or Python slicing). Never retype it. Then fix imports.
5. Delete or shrink the old module only after the new one imports and the tests pass.
6. When you swap a loop for a dict/set/sort, keep the order, tie and duplicate rules (first vs last wins). Test with duplicates.
7. After every file: run the tests, the scripts and diff against before_*.txt. Any diff: fix it before going on.
8. Check structural rules with code (grep -c 'def name', an ast scan), not by reading.
9. If it must be faster: time it, profile (python3 -m cProfile -s cumtime) if still over the limit, do not guess.
Harness already does: prompt rules 12-13 (copy line ranges, save before.txt), tests gate at finish, compile check on edit.
```

## investigate: Investigation (find the cause in code, logs or data; then fix or report)

```
1. List and read the relevant code and a sample of the data (head, wc -l). Read the whole module, not one function.
2. Run the failing command or tests once and save the output in /tmp.
3. Pick the smallest input that shows the problem and work out the right answer by hand from the task.
4. Follow it through each stage (parse, store, query, output); print the value after each stage with a short script in /tmp.
5. The first stage that differs from your hand result has the bug. Edit there in the next step.
6. Count and compare with code (wc -l, len, sort | uniq -c), never by eye; line numbers from read_file are not data.
7. Two probes with the same output: stop probing, change the code or the hypothesis. Do not rename debug scripts to vary them.
8. Expect several causes. After each fix, re-run everything and repeat 3-5 for what still fails.
9. Then check each requirement the visible tests do not cover. Write reports from the real inputs and cat them.
Harness already does: debug rules 15-18 only in v7i (not v7e); stagnation nudge after 10 steps with no file change.
```

## scratch: New script / CLI from scratch

```
1. ls the work dir and read every provided input file (head, wc -l). Note exact names, formats and output wording.
2. Write .agent/spec_test.py first. Line 1: import sys; sys.path.insert(0, '/work'). One assert per example and rule.
3. Add interaction asserts: mixed input, constructs adjacent without separators, duplicates, empty input, error cases.
4. Fixtures only in tempfile.mkdtemp(). spec_test must never write or delete the real input or output files.
5. Put test strings with backticks, $ or quotes in a file or a <<'EOF' heredoc, never inside python3 -c "...".
6. Write the program; if it is long, write it in parts (write, then mode=append). Resolve paths from argv, not the cwd.
7. Run spec_test. On a failure decide from the task text whether the code or the assert is wrong.
8. Run the real command from another dir (cd /tmp && python3 /work/prog.py ...); check the resulting files and run it twice.
9. Last: run on the real inputs, cat the real output, compare its format with the task character by character.
Harness already does: spec_test must exist and pass at finish (run from .agent/, so the sys.path line matters), restores modified inputs once, compile check.
```

## Before finish

```
1. The last edit was followed by a run of: the full existing test suite, .agent/spec_test.py, and the real program on the real inputs.
2. Each requirement sentence of the task has an assert or a command whose output you read, including the 'do not' rules.
3. The real output files exist, came from the real inputs, and match the task's format character by character (cat them).
4. Run it the way the grader does (other cwd, PYTHONPATH, python3 -m) at least once.
5. No test data, scratch configs or debug scripts left in the project; inputs and tests unchanged; spec_test has no side effects on /work.
6. Every public def/class that existed before still exists (if you rewrote files).
7. No traceback, non-zero exit or over-limit number in your last outputs.
Harness already runs at finish: compileall, the project's tests (rejects if failing), spec_test (rejects if missing/failing), input-restore check, an LLM judge. Do not spend steps duplicating those; spend them on items 2-6, which no gate checks.
```

# Standalone playbooks (bare loop: bash, read_file, write_file, edit_file, finish only)

For a plain tool loop with no spec_test gate, todo, judge, repeat guard or compile check. Each ends with a note for when the v7e harness is present. The extra steps (never repeat a call, write big files in parts, call finish when done, line-number-free old_text) come from the bare v0/v1 runs (see 'Bare vs harnessed' in lessons-v8.md).

## bare bugfix: Bug fix in an existing codebase (bare loop: bash, read_file, write_file, edit_file, finish)

```
1. ls -R, then read the entry point, the modules on the failing path and the tests (cat a b c in one command).
2. Run the tests or the failing command once; save the output: ... > /tmp/before.txt 2>&1.
3. Write /tmp/repro.py with the smallest failing input and the correct result from the task text.
4. Edit as soon as you can name the cause. old_text is file text without the line-number prefix.
5. After each edit: python3 /tmp/repro.py and the full test suite. Never run the same command twice in a row unchanged.
6. Same output twice: change the code or the hypothesis, not the probe. Same fix failed twice: re-read the source.
7. Fix where the bad value is produced, not in a caller. Expect more than one bug.
8. Tests green is not done: check each task requirement the tests do not cover with one command each.
9. Then call finish. Do not use up the remaining steps.
With v7e: tests and spec_test are also gated at finish; repeats are refused; edits are compile-checked.
```

## bare feature: Feature addition with a long spec (bare loop)

```
1. Read the spec, the entry point, the wiring (main/router/__init__), the modules to change and the tests. Run the tests once.
2. Write /tmp/req.txt: one line per spec sentence, including every 'do not', 'only' and 'keep' rule.
3. Work one subsection at a time: asserts in /tmp/test_new.py, then the code, then that file + the existing tests.
4. Expected values come from the spec text, never from your program's output. Add combined and adjacent cases.
5. Change existing files with small edit_file edits. Before a whole-file rewrite: cp f /tmp/f.orig; afterwards grep that every def/class is still there.
6. Write long files in parts (first part with write_file, then append with cat >> f <<'EOF'). One huge call can crash the run.
7. A failing assert: quote the spec line before changing code or assert.
8. Run the CLI the way it is graded: cd /tmp && PYTHONPATH=/work python3 -m pkg ...; compare with the spec character by character.
9. Re-run the existing tests and the old commands last; then call finish.
With v7e: write the asserts as .agent/spec_test.py (it is gated at finish) and use todo for step 2.
```

## bare refactor: Refactor / migration preserving behaviour (bare loop)

```
1. Read all modules, scripts and tests involved. Run the tests and every script once.
2. Freeze the baseline ONCE: cp -r the package /tmp/orig; save each output to /tmp/before_*.txt. Never regenerate it.
3. New inputs: make their expected output by running /tmp/orig, never the code you are changing.
4. Move code by line range: sed -n 'A,Bp' old.py >> new.py. Never retype it. Then fix imports.
5. Remove the old code only after the new module imports and the tests pass.
6. Swapping a loop for a dict/set/sort: keep order, tie and duplicate rules. Test with duplicates.
7. After every file: tests, scripts, diff against /tmp/before_*.txt. Fix any diff before going on.
8. Check structure rules with code (grep -c, an ast scan). Speed limits: time it; profile if still slow.
9. Call finish when the diffs are empty and the tests pass.
With v7e: the prompt already asks for line-range copies and .agent/before.txt; tests are gated at finish.
```

## bare investigate: Investigation (find the cause, then fix or report) (bare loop)

```
1. Read the relevant code (whole modules) and a sample of the data (head, wc -l).
2. Run the failing command once; save the output in /tmp.
3. Pick the smallest input that shows the problem; work out the right answer by hand from the task.
4. Print the value after each stage (parse, store, query, output) with a short script in /tmp.
5. The first stage that differs from the hand result has the bug. Edit there in the next step.
6. Count with code (wc -l, len, sort | uniq -c), never by eye. Line numbers from read_file are not data.
7. Never send the same probe twice; never vary only a file name or a comment. Change code or hypothesis.
8. After each fix re-run everything; repeat 3-5 for what still fails.
9. Write reports from the real inputs; cat them; call finish.
With v7e: a nudge fires after 10 steps with no file change; that is too late - follow step 7 yourself.
```

## bare scratch: New script / CLI from scratch (bare loop)

```
1. ls and read every input file (head, wc -l). Note exact file names, formats and output wording.
2. Write /tmp/test_prog.py first: one assert per example and rule; mixed, adjacent, duplicate, empty and error cases.
3. Fixtures only in tempfile.mkdtemp(). Never write test data into the task's input or output files.
4. Test strings with backticks, $ or quotes go in a file or a <<'EOF' heredoc, never in python3 -c "...".
5. Write the program; long files in parts. Resolve paths from argv, not the cwd.
6. Run the tests after every change. Exact same command twice in a row means stop and change something.
7. A failing assert: decide from the task text whether the code or the assert is wrong.
8. Run the real command from another dir; check the resulting files; run it twice.
9. Last: run on the real inputs, cat the output, compare its format with the task character by character, call finish.
With v7e: put the tests in .agent/spec_test.py with sys.path.insert(0, '/work') at the top; it is re-run at finish.
```

## Before finish (bare)

```
1. After the last edit you ran: the full test suite, your own asserts, and the real program on the real inputs.
2. Every requirement sentence of the task has a check whose output you read, including the 'do not' rules.
3. Output files exist, come from the real inputs, and match the task format character by character.
4. Inputs, provided tests and unrelated files are unchanged; no test data or scratch files left in /work.
5. Every def/class that existed before still exists.
6. No traceback, non-zero exit or over-limit number in your last outputs.
7. Call finish now. Do not spend the remaining steps re-running the same checks.
```
