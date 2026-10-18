"""Harness variants for agent.py. Each profile = system prompt + loop hooks.
v0: bare loop (baseline). Later versions add prompt, loop and verification engineering."""
import json, re

V0_SYSTEM = """You are a coding agent working in a Linux container. The task files are in /work.
Use the tools to complete the user's task. Call finish when done."""

V1_SYSTEM = """You are an expert software engineer working as an autonomous agent in a Linux container (Python 3.12, bash, no network). The task files are in /work.

How to work:
1. Explore first: list the files (ls -la, find) and read the relevant ones before changing anything.
2. Make a short plan, then act. Prefer small, precise edits (edit_file) over rewriting whole files.
3. Verify: run the code, the tests, or a quick script that checks the result against every requirement in the task. Read the output carefully.
4. If something fails, read the error, find the cause, fix it and verify again. Never guess or claim success without evidence.
5. Follow the task's exact file names, formats and output wording. Do not change files the task did not ask you to change (tests included).
6. When every requirement is met and verified, call finish with a short summary.

Tool tips: bash runs `bash -lc` in /work with a 60 s limit. Use python3 for scripts. read_file shows line numbers; edit_file needs old_text copied exactly from the file (without the line-number prefix)."""


class LoopState:
    def __init__(self):
        self.no_call = 0
        self.finish_tries = 0
        self.recent = []
        self.streak = 0          # consecutive repeats of the same action
        self.hot = 0             # steps left with raised temperature


def view(messages, prof):
    return messages


def on_no_call(state, prof, content):
    """The model answered without a tool call. Return a nudge message to continue, or None to stop."""
    if not prof.get("nudge"):
        return None
    state.no_call += 1
    if state.no_call > 3:
        return None
    return ("Continue working with the tools. If the task is complete and verified, call the finish tool. "
            "Do not ask the user questions; make reasonable choices and proceed.")


def on_finish(state, prof, box, task, messages, args):
    """Return None to accept finish, or a message that sends the model back to work."""
    if not prof.get("verify_finish"):
        return None
    state.finish_tries += 1
    if state.finish_tries > 2:
        return None
    return ("Before finishing, verify against the task. Re-read the task, list each requirement, and check each one "
            "with a command (run the program/tests, cat the output files). Fix anything that is off, then call finish again.")


def before_tool(state, prof, name, args):
    """Return an observation to skip running the tool (e.g. an exact repeat), or None to run it."""
    if not prof.get("skip_repeats") or args is None:
        return None
    key = name + json.dumps(args, sort_keys=True)
    if name != "bash" or not state.recent or state.recent[-1] != key:
        return None
    state.repeats = getattr(state, "repeats", 0) + 1
    return ("[harness] This is exactly the same action as your previous step, so it was not run again (the result would be the same). "
            "Look at the previous result and decide a different next step. If the task is done, verify it once and call finish.")


def on_observation(state, prof, name, args, obs):
    if not prof.get("loop_guard") or args is None:
        return obs
    key = name + json.dumps(args, sort_keys=True)
    state.recent.append(key)
    if state.recent[-8:].count(key) >= 3:
        obs += "\n[harness] You have run this exact action 3 times. It will not give a different result; try a different approach."
    return obs


PROFILES = {
    "v2": {"system": V1_SYSTEM, "max_steps": 40, "temperature": 0.3, "max_tokens": 4096, "nudge": True, "verify_finish": True,
           "loop_guard": True, "skip_repeats": True, "robust_api": True, "smart_edit": True},
    "v3": {"system": V1_SYSTEM, "max_steps": 40, "temperature": 0.3, "max_tokens": 4096, "nudge": True, "verify_finish": True,
           "loop_guard": True, "skip_repeats": True, "robust_api": True, "smart_edit": True, "break_loops": True},
    "v0": {"system": V0_SYSTEM, "max_steps": 30, "temperature": 0.3},
    "v1": {"system": V1_SYSTEM, "max_steps": 40, "temperature": 0.3, "nudge": True, "verify_finish": True, "loop_guard": True},
}


def temperature(state, prof):
    if state.hot > 0:
        state.hot -= 1
        return 0.9
    return prof["temperature"]


def is_repeat(state, name, args):
    """True if this call equals the previous call (the attractor that makes small models loop)."""
    key = name + json.dumps(args, sort_keys=True) if args is not None else name
    rep = bool(state.recent) and state.recent[-1] == key
    state.streak = state.streak + 1 if rep else 0
    return rep


BREAK_MSG = ("[harness] You are stuck repeating the same action. Stop and decide now: "
             "(a) if the task's requirements are already met, call finish; "
             "(b) otherwise take ONE different action that makes progress (edit a file, run a different check).")
