class TsError(Exception):
    """Runtime failure: printed as 'error: <message>', exit status 1."""
    exit_code = 1


class UsageError(TsError):
    """Bad command-line value: printed as 'error: <message>', exit status 2."""
    exit_code = 2


class ConfigError(TsError):
    """Bad or missing config: printed as 'error: config: <message>', exit status 2."""
    exit_code = 2
