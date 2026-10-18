# local-agent

A Claude-Code-style coding agent for local models (llama-server, OpenAI-compatible API), plus the harness
engineering and evaluation needed to make a small model act reliably.

Everything runs locally: no paid APIs, no network access from the agent (commands run in a network-less
podman container that only sees the task workspace).

## Layout

| Path | What it is |
|---|---|
| `agent.py` | Tool loop: bash, read_file, write_file, edit_file, finish. Sandbox = podman `python:3.12-slim`, `--network none`. |
| `harness_profiles.py` | Harness variants (system prompt, nudges, finish verification, loop guard). `v0` = bare baseline. |
| `make_tasks.py` | Writes the task suite (`tasks/<id>/task.md`, seed `files/`, hidden `check/check.sh`). Instructions are Japanese. |
| `refs.py` | Reference solutions; proves every check can pass. |
| `eval.py` | Runs the suite with one profile and grades it. Results in `runs/<profile>-<time>/`. |
| `bfcl_proxy/harness.py` | Responses-API proxy used for BFCL experiments (prompt, schema repair, fast boolean judge). |

## Usage

```sh
python3 make_tasks.py          # generate tasks/
python3 refs.py                # sanity: all reference solutions pass
python3 eval.py v1             # run the suite with profile v1 (model server on :8085)
```
