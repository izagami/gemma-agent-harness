import contextlib
import io
import os
import tempfile

from ts.cli import main


class Workspace:
    """Run ts.cli.main inside a temporary working directory."""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def write(self, name, text):
        path = os.path.join(self.dir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def run(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        old = os.getcwd()
        os.chdir(self.dir)
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                try:
                    code = main(list(argv))
                except SystemExit as e:
                    code = e.code
        finally:
            os.chdir(old)
        return code, out.getvalue(), err.getvalue()

    def close(self):
        self._tmp.cleanup()
