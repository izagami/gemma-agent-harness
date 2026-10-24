"""Procedural knowledge for the agent's system prompt: playbooks, lessons and the before-finish checklist mined from
past trajectories (docs/lessons-v8.json, see docs/lessons-v8.md). ctx = "bare" (plain tool loop) or "v7e" (full harness)."""
import json, os

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "lessons-v8.json")


def text(ctx):
    d = json.load(open(PATH, encoding="utf-8"))
    books = d["playbooks_bare"] if ctx == "bare" else d["playbooks"]
    finish = d["before_finish_bare"] if ctx == "bare" else d["before_finish"]
    lessons = [l["text"] for l in d["lessons"] if ctx in l.get("contexts", ["bare", "v7e"])]
    return ("\n\n# How to work (playbooks)\nFirst decide which kind of task this is, then follow that playbook.\n\n"
            + "\n\n".join(books.values())
            + "\n\n# " + finish.strip()
            + "\n\n# Lessons from past failures\n" + "\n".join(f"- {t}" for t in lessons))
