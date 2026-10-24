#!/usr/bin/env python3
"""Tier v8: held-out suite (z_* ids) for measuring process improvements (playbooks / experience memory).

Everything for a task lives in v8/<id>/:
  task.md      instruction given to the agent
  check.sh     hidden check (runs as `bash /check/check.sh` in the sandbox, /work = agent workspace; exit 0 = pass)
  seed/        workspace the agent starts from            -> tasks_v8/<id>/files/
  hidden/      extra files available to the check         -> tasks_v8/<id>/check/
  ref/         reference solution, overlaid on the seed (used only by validate_v8.py)
  ref_cmd.sh   optional shell run in /work after the overlay (e.g. deleting files)

usage: python3 tasks_v8.py          # (re)build tasks_v8/ (same layout as tasks/)
       TASKS_DIR=$PWD/tasks_v8 python3 evalmulti.py PROFILE
Files are copied byte for byte (some seeds are deliberately not UTF-8).
"""
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.environ.get("SUITE_SRC", os.path.join(HERE, "v8"))
OUT = os.environ.get("SUITE_OUT", os.path.join(HERE, "tasks_v8"))

# id -> (kind, one-line description)
TASKS = {
    "z_billing_periods": ("debug", "subscription invoices wrong after month-end anchors; bug in period arithmetic two modules away"),
    "z_footnote_leak": ("debug", "batch-rendered docs get footnotes/state from earlier docs (shared mutable state)"),
    "z_vendor_import": ("debug", "customer importer garbles/duplicates some vendor files (encoding sniff + normalization)"),
    "z_price_cache": ("debug", "order totals stale after tier change: cache invalidation event never fires"),
    "z_expense_report": ("feature", "add `report` subcommand with exact formats, rounding, ordering, errors, idempotent import"),
    "z_ssg_tags": ("feature", "static site generator: tag pages + index, slugs, drafts, idempotent/stale cleanup"),
    "z_migrations": ("feature", "sqlite migration runner: status/apply/dry-run, ordering, gap errors, rollback"),
    "z_settings_migrate": ("refactor", "replace global legacy settings module with explicit Settings object, behavior identical"),
    "z_cmd_registry": ("refactor", "split if/elif god-module CLI into per-command modules + registry, output identical"),
    "z_region_totals": ("investigate", "find why the kansai monthly total disagrees with accounting; fix the cause"),
    "z_incident_logs": ("investigate", "reconstruct an incident from multi-service logs, write incident.json, fix retry bug"),
    "z_tsel_cli": ("cli", "column-select/filter CLI from scratch with stdin, exit codes, exact errors + tests"),
}


def ids():
    return sorted(t for t in os.listdir(SRC) if os.path.isfile(os.path.join(SRC, t, "task.md")))


def _copytree(src, dst):
    if os.path.isdir(src):
        shutil.copytree(src, dst, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    else:
        os.makedirs(dst, exist_ok=True)


def build_one(tid, base):
    """Write one task in the tasks/ layout to base/ (= .../<tid>)."""
    s = os.path.join(SRC, tid)
    shutil.rmtree(base, ignore_errors=True)
    os.makedirs(base)
    _copytree(os.path.join(s, "seed"), os.path.join(base, "files"))
    _copytree(os.path.join(s, "hidden"), os.path.join(base, "check"))
    shutil.copy(os.path.join(s, "task.md"), os.path.join(base, "task.md"))
    if os.path.exists(os.path.join(s, "sandbox.json")):  # per-task image/mounts for the agent and the check
        shutil.copy(os.path.join(s, "sandbox.json"), os.path.join(base, "sandbox.json"))
    chk = open(os.path.join(s, "check.sh"), encoding="utf-8").read()
    if not chk.startswith("#!"):
        chk = "#!/bin/bash\n" + chk
    with open(os.path.join(base, "check", "check.sh"), "w", encoding="utf-8") as f:
        f.write(chk)


def build(root=OUT):
    tmp = root + ".new"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    for tid in ids():
        build_one(tid, os.path.join(tmp, tid))
    if os.path.isdir(root):
        os.rename(root, root + ".old")
    os.rename(tmp, root)
    shutil.rmtree(root + ".old", ignore_errors=True)
    return ids()


if __name__ == "__main__":
    print(len(build()), "tasks ->", OUT)
