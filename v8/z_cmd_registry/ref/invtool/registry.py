"""Command registry: every module in invtool/commands/ registers itself with @command."""
import importlib
import pkgutil
from dataclasses import dataclass
from typing import Callable

_COMMANDS = {}


class CommandError(Exception):
    def __init__(self, msg, code=1):
        super().__init__(msg)
        self.code = code


@dataclass(frozen=True)
class Command:
    name: str
    usage: str
    summary: str
    func: Callable


def command(name, usage, summary):
    def deco(func):
        _COMMANDS[name] = Command(name, usage, summary, func)
        return func
    return deco


def load_all():
    import invtool.commands as pkg
    for m in pkgutil.iter_modules(pkg.__path__):
        if not m.name.startswith("_"):
            importlib.import_module(f"{pkg.__name__}.{m.name}")
    return dict(_COMMANDS)


def get(name):
    load_all()
    return _COMMANDS.get(name)


def all_commands():
    return [_COMMANDS[n] for n in sorted(load_all())]
