"""Config file parser. Format (docs/SPEC.md, "Config file"):

    # comment            ; also a comment
    data = entries.tsv
    [project.alpha]
    rate = 6000
    name = "Alpha Corp"

Keys before the first [section] belong to the top-level section "".
A later assignment of the same key in the same section overrides the earlier one.
"""
import os

from ts.errors import ConfigError


class Config:
    def __init__(self, values=None, path=None):
        self.values = dict(values or {})     # (section, key) -> str
        self.path = path                     # main config file, or None when no config is used

    def get(self, key, default=None, section=""):
        return self.values.get((section, key), default)

    def section(self, name):
        return {k: v for (s, k), v in self.values.items() if s == name}

    @property
    def base_dir(self):
        """Directory that relative paths in the config are resolved against."""
        return os.path.dirname(os.path.abspath(self.path)) if self.path else os.getcwd()


def _unquote(value):
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def parse(text, path=None):
    values = {}
    section = ""
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("["):
            name = line[1:-1].strip()
            if not line.endswith("]") or not name:
                raise ConfigError(f"line {n}: bad section header")
            section = name
            continue
        if "=" not in line:
            raise ConfigError(f"line {n}: expected key = value")
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            raise ConfigError(f"line {n}: empty key")
        values[(section, key)] = _unquote(value.strip())
    return Config(values, path)


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        raise ConfigError(f"not found: {path}") from None
    return parse(text, path)
