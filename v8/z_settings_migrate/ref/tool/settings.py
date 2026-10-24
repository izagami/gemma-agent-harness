"""Explicit settings object: load once, pass it to every function that needs configuration."""
import configparser
import os

TRUE = {"1", "yes", "on", "true"}
FALSE = {"0", "no", "off", "false", ""}


def _clean(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] == '"':
        v = v[1:-1]
    return v


class Settings:
    def __init__(self, values=None, overrides=None):
        self._values = dict(values or {})
        self._overrides = {k.lower(): v for k, v in (overrides or {}).items()}

    @classmethod
    def load(cls, path=None, env=None, overrides=None):
        env = os.environ if env is None else env
        explicit = path is not None
        if path is None:
            path = env.get("TOOL_CONFIG") or "tool.ini"
        values = {}
        if os.path.exists(path):
            cp = configparser.ConfigParser(interpolation=None)
            with open(path, encoding="utf-8") as f:
                cp.read_file(f)
            for sec in cp.sections():
                for k, v in cp.items(sec):
                    values[f"{sec.lower()}.{k.lower()}"] = _clean(v)
        elif explicit:
            raise FileNotFoundError(f"config file not found: {path}")
        for name, v in sorted(env.items()):
            if not name.startswith("TOOL_") or "__" not in name[5:]:
                continue
            sec, key = name[5:].split("__", 1)
            full = f"{sec.lower()}.{key.lower()}"
            if v == "":
                values.pop(full, None)
            else:
                values[full] = _clean(v)
        return cls(values, overrides)

    def _raw(self, key):
        key = key.lower()
        if key in self._overrides:
            return self._overrides[key]
        return self._values.get(key)

    def get(self, key, default=None):
        v = self._raw(key)
        return default if v is None else v

    def get_int(self, key, default=None):
        v = self._raw(key)
        if v is None:
            return default
        try:
            return int(v.replace("_", ""))
        except ValueError:
            raise ValueError(f"setting {key}: not an integer: {v!r}") from None

    def get_bool(self, key, default=None):
        v = self._raw(key)
        if v is None:
            return default
        s = v.strip().lower()
        if s in TRUE:
            return True
        if s in FALSE:
            return False
        raise ValueError(f"setting {key}: not a boolean: {v!r}")

    def get_list(self, key, default=None):
        v = self._raw(key)
        if v is None:
            return list(default or [])
        return [x.strip() for x in v.replace("\n", ",").split(",") if x.strip()]

    def items(self):
        merged = dict(self._values)
        merged.update(self._overrides)
        return sorted(merged.items())
