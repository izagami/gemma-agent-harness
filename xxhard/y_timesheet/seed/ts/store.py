"""Entries are stored in a tab-separated file: date, project, minutes, note (one entry per line)."""
import os
from dataclasses import dataclass

from ts.errors import TsError


@dataclass
class Entry:
    date: str        # YYYY-MM-DD
    project: str
    minutes: int
    note: str = ""


def load_entries(path):
    if not os.path.exists(path):
        return []
    entries = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) != 4 or not parts[2].isdigit():
                raise TsError(f"{os.path.basename(path)}: line {n}: corrupt entry")
            entries.append(Entry(parts[0], parts[1], int(parts[2]), parts[3]))
    return entries


def append_entry(path, entry):
    note = entry.note.replace("\t", " ").replace("\n", " ")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{entry.date}\t{entry.project}\t{entry.minutes}\t{note}\n")
