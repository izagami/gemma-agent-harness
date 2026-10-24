# local-agent

A Claude-Code-style coding agent for **local models**, usable from **Open WebUI**. A harness (prompting, loop
control, verification, fast typed judgments) lets a ~12B open model work reliably on multi-step coding tasks.
Everything runs on your own machine: no paid APIs, and the commands the model runs cannot reach the internet.

> Status: private preview. License: **Apache-2.0** (see LICENSE and NOTICE).

## What you get

- **Agent server** (`deploy/agent_server.py`): OpenAI-compatible endpoint that exposes the agent as the model
  `local-agent`. Each chat gets its own workspace. While it works, the steps stream into a collapsible
  "作業ログ" block; the result lists the files it changed.
- **Sandbox** (`deploy/sandbox_server.py`): a separate container on an internal-only network that runs the
  model's shell commands in the workspace (read-only root, no capabilities, memory/pid limits).
- **Open WebUI pipe** (`openwebui/local_agent_pipe.py`): optional one-file integration.
- **Harness** (`agent_v5.py`, profile `v6f`): see "How the harness works".

## Quick start (Docker / Podman)

1. Run a model server with tool calling, e.g. llama.cpp:
   `llama-server -m gemma-4-12B-it-qat-UD-Q4_K_XL.gguf --jinja -ngl 999 -c 65536 --port 8080`
   (one request at a time is fastest on small GPUs; the agent server serialises tasks).
2. `cp deploy/.env.example deploy/.env` and set `AGENT_API`, `AGENT_MODEL`, `SERVER_API_KEY`.
3. `docker compose -f deploy/compose.yaml up -d --build`
4. Open WebUI → Admin Settings → Connections → add `http://<host>:8094/v1` with the key from step 2.
   Pick **local-agent** in the model list and give it a task.

Without Docker: `SANDBOX_URL` unset makes the server use a local podman sandbox (`--network none`) per task:
`WORKSPACE_ROOT=~/agent-workspaces AGENT_API=http://127.0.0.1:8080/v1/chat/completions python3 deploy/agent_server.py`

## How the harness works (v6f)

| Problem seen with small models | What the harness does |
|---|---|
| Repeats the same command 15-30 times | Repeats are not run; the model gets the previous result, never its own call text echoed back |
| Tool call cut off at the token limit poisons the history (every later request fails) | Unparsable arguments never enter the history; retries at higher temperature with a smaller cap |
| Reasons inside bash comments until the call is cut off | `think` tool, short thoughts, nudge after two in a row |
| `edit_file` fails on indentation | Whitespace-tolerant match with re-indent, closest-line hint, py_compile check with rollback |
| Finishes without checking the spec | Test-first: `.agent/spec_test.py` with an assert per requirement, run by the harness before finish |
| Overwrites input data to test its code | Original bytes are kept; a fast judgment decides per changed file whether the task asked to modify it, otherwise it is restored |
| Loses track in long tasks | `todo` checklist shown every turn; old tool outputs masked in one batch (keeps the prompt cache warm) |
| Says "done" too early | Harness compiles all Python files, runs found tests, and asks a fast boolean judge (JSON-schema constrained, logprob confidence) inside the agent's own context |

## Results (Gemma 4 12B QAT, thinking off, 1× Intel Arc Pro B70)

| Suite | v0 (bare loop) | v6 / v6f |
|---|---|---|
| 40 tasks (20 easy, 15 hard, 5 multi-file) | 27/35 on the first 35 | **39/40** |
| 5 repo-scale tasks (400-550 lines, 6-16 files) | - | 0/5 (step limit; next target) |

Task suite: `make_tasks.py`, `tasks_hard.py`, `tasks_xhard.py`, `tasks_xxhard.py`; every hidden check fails on the
seed and passes with the reference solution (`refs.py`). Run: `python3 eval.py v6f`.

## Harness v9 (2026-10, Gemma 4 26B-A4B, vLLM on 3× Intel Arc Pro B70)

Current best configuration (profile `v7o` plus environment flags; run through `cycle.py` / `run_vllm.sh`):

    THINK_SCHEMA=3 THINK_LEARNED=800 THINK_NEXT=400 AGENT_TEMP=0 EDIT2=1 MIDGATE=1 KNOW=1 LINT=1 EDIT3=1

| Flag | What it does |
|---|---|
| `THINK_SCHEMA=3` … | the `think` tool is a short typed answer (last result / learned / next) fused with the next action |
| `AGENT_TEMP=0` | greedy decoding: fewer random failures and less run-to-run noise |
| `EDIT2` | edits survive misremembered `old_text` (line alignment, never deleting lines the model did not know about), show the file's current text on failure, catch no-op edits, refuse a third blind rewrite of the same file |
| `MIDGATE` | the finish gate (`evidence.py`: run the task's commands on a fresh copy, then judge every requirement with a fast logprob judge) also runs in the background at 35 % / 65 % of the time limit and reports violations |
| `KNOW` | `know.py`: domain sheets (VBA port, browser automation, SQLite, firewall audit, exact output files) plus all docs/code in the first message. The sheets are the facts a strong model used to solve the tasks this model failed - general facts of each domain, not answers |
| `LINT` | the sheets as checks on every written file (e.g. `executescript` inside `BEGIN`, `open(..., "w")` without `newline=""`, `//` for VBA `\`, `time.sleep` in Playwright) |
| `EDIT3` | stops tool calls that turn into reasoning in code comments or prose (they used to run to the token limit), writes path-less test/CAD files to their usual path, warns when a rewrite drops a function |

Evaluation: `tasks_qg/` (25 tasks with graded hidden checks), `tasks_v8/` (12), and `tasks_h/` (7 held-out tasks in the
same domains, written by separate agents that never saw `know.py`; reference solutions in `tasks_h_ref/`).
`score_task.py TASKDIR WORKDIR` scores a work directory exactly like `eval.py`. `cycle.py BASE CAND [tasks]` runs two
configurations side by side on the same tasks and prints a paired comparison.

Measured on tasks never used to build the sheets (`tasks_h`, 4 runs per task per configuration):
mean graded score 0.291 → 0.418 (VBA inventory valuation 0.01 → 0.53, browser inventory export 0.00 → 0.47,
firewall audit 0.42 → 0.70). On the 9 tasks the sheets came from: 0.30 → 0.54, 4 passes vs 0.

## Security notes

- Treat the model as untrusted: it only runs commands inside the sandbox container, which has no network.
- Set `SERVER_API_KEY` unless the server is reachable only by you. Bind to `127.0.0.1` by default (compose does).
- Workspaces persist in the `workspaces` volume; delete them when you no longer need the files.

## License

Apache License 2.0. Copyright 2026 eaither-game. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
