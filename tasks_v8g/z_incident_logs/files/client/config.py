"""Load the retry policy from a service's ini file (see config/orders.ini)."""
import configparser

from client.retry import RetryPolicy

DEFAULTS = {
    "max_attempts": 6,
    "base_delay_ms": 100,
    "multiplier": 2.0,
    "max_delay_ms": 5000,
    "retry_on": (502, 503, 504),
}


def _ints(text):
    return tuple(int(x) for x in str(text).split(",") if x.strip())


def load_retry_policy(path, section="retries"):
    cp = configparser.ConfigParser()
    cp.read(path, encoding="utf-8")
    values = dict(DEFAULTS)
    if cp.has_section(section):
        s = cp[section]
        for key in ("max_attempts", "base_delay_ms", "max_delay_ms"):
            if key in s:
                values[key] = s.getint(key)
        if "multiplier" in s:
            values["multiplier"] = s.getfloat("multiplier")
        if "retry_on" in s:
            values["retry_on"] = _ints(s["retry_on"])
    return RetryPolicy(**values)
