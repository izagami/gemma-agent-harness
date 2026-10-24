"""Process-wide settings (legacy).

Usage: legacy_settings.reload(path) once at start-up, then legacy_settings.get("section.key", default)
from anywhere.  Everything lives in module globals.

Rules (other modules and users rely on all of these):
- File: reload(path).  With path=None the file is $TOOL_CONFIG, else ./tool.ini, and a missing file
  just means "no settings".  A path passed explicitly must exist: FileNotFoundError("config file not found: PATH").
- INI syntax (configparser, no interpolation).  Keys are "section.key", case-insensitive.
  Values in [DEFAULT] are inherited by every section of the file (not by sections that only come from env).
- Values are stripped, and one pair of surrounding double quotes is removed ("  x " -> x, "\"a b\"" -> a b).
- Environment: TOOL_<SECTION>__<KEY>=value overrides the file (split at the first "__"; names are
  lower-cased; TOOL_MAIL_OUT__FROM_ADDR -> mail_out.from_addr).  An env var set to the empty string
  *removes* the key, so callers get their default.  Env values are cleaned like file values.
- Overrides (set_override, used by --set) beat file and env.  They are not cleaned and an empty
  override is an empty value (not a removal).  reload() keeps overrides.
- get(key, default) returns the raw (cleaned) string or default.
- get_int: int() after removing "_" ("1_000" -> 1000, " -3 " -> -3); error ValueError("setting KEY: not an integer: 'RAW'").
- get_bool: 1/yes/on/true -> True, 0/no/off/false/"" -> False (case-insensitive, stripped);
  error ValueError("setting KEY: not a boolean: 'RAW'").
- get_list: split at commas and newlines, strip items, drop empty items; missing -> list(default or []).
- Typed getters return default unchanged when the key is missing.
- items(): sorted [(key, value)] of everything currently set.
"""
import configparser
import os

_values = {}
_overrides = {}
_loaded = False

TRUE = {"1", "yes", "on", "true"}
FALSE = {"0", "no", "off", "false", ""}


def _clean(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] == '"':
        v = v[1:-1]
    return v


def reload(path=None, env=None):
    global _values, _loaded
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
    _values = values
    _loaded = True


def set_override(key, value):
    _overrides[key.lower()] = value


def clear_overrides():
    _overrides.clear()


def _raw(key):
    if not _loaded:
        reload()
    key = key.lower()
    if key in _overrides:
        return _overrides[key]
    return _values.get(key)


def get(key, default=None):
    v = _raw(key)
    return default if v is None else v


def get_int(key, default=None):
    v = _raw(key)
    if v is None:
        return default
    try:
        return int(v.replace("_", ""))
    except ValueError:
        raise ValueError(f"setting {key}: not an integer: {v!r}") from None


def get_bool(key, default=None):
    v = _raw(key)
    if v is None:
        return default
    s = v.strip().lower()
    if s in TRUE:
        return True
    if s in FALSE:
        return False
    raise ValueError(f"setting {key}: not a boolean: {v!r}")


def get_list(key, default=None):
    v = _raw(key)
    if v is None:
        return list(default or [])
    return [x.strip() for x in v.replace("\n", ",").split(",") if x.strip()]


def items():
    if not _loaded:
        reload()
    merged = dict(_values)
    merged.update(_overrides)
    return sorted(merged.items())
