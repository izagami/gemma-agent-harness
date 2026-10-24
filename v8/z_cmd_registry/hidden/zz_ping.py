import os

from invtool.registry import CommandError, command


@command("ping", usage="ping [WORD...]", summary="reply with pong")
def ping(args, data):
    if args == ["fail"]:
        raise CommandError("ping failed", 3)
    print("pong", *args, os.path.basename(data))
    return 0
