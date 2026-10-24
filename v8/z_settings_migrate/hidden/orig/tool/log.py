"""Diagnostics on stderr, enabled by general.verbose."""
import sys

from tool import legacy_settings


def info(msg):
    if legacy_settings.get_bool("general.verbose", False):
        prefix = legacy_settings.get("general.log_prefix", "[tool]")
        print(f"{prefix} {msg}", file=sys.stderr)
