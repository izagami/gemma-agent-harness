# local-agent

A Claude-Code-style coding agent for **local models**, usable from **Open WebUI**. A harness (prompting, loop
control, verification, fast typed judgments) lets a ~12B open model work reliably on multi-step coding tasks.
Everything runs on your own machine: no paid APIs, and the commands the model runs cannot reach the internet.

> Status: private preview. License: **TBD** (not yet chosen; do not redistribute).

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

## Security notes

- Treat the model as untrusted: it only runs commands inside the sandbox container, which has no network.
- Set `SERVER_API_KEY` unless the server is reachable only by you. Bind to `127.0.0.1` by default (compose does).
- Workspaces persist in the `workspaces` volume; delete them when you no longer need the files.
