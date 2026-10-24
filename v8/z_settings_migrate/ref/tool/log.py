"""Diagnostics on stderr, enabled by general.verbose."""
import sys

def info(msg, settings):
    if settings.get_bool("general.verbose", False):
        prefix = settings.get("general.log_prefix", "[tool]")
        print(f"{prefix} {msg}", file=sys.stderr)
