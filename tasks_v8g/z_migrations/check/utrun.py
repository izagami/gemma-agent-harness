"""Graded unittest runner for tasks_v8g (a copy lives in every check/ dir).

usage: python3 /check/utrun.py [--file /check/test_x.py] [--suite] MODULE=N ...

Default mode runs exactly what `python3 -m unittest discover -s tests -q` runs (cwd on sys.path, tests/ as the top
level) and exits like it (1 = failures/errors, 5 = no tests ran, Python 3.12). --file runs one test file the way
`python3 FILE -q` does (its directory on sys.path). Prints `ITEMS k/n` last: one item per test case of each listed
MODULE (N = its expected test count, fixed), plus with --suite one item "the whole suite passed" (this also covers
tests the agent added, which are not counted one by one)."""
import importlib, os, sys, unittest

args = sys.argv[1:]
fname = None
suite_item = False
expect = {}
while args:
    a = args.pop(0)
    if a == "--file":
        fname = args.pop(0)
    elif a == "--suite":
        suite_item = True
    else:
        m, n = a.split("=")
        expect[m] = int(n)


class Result(unittest.TextTestResult):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.passed = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed.append(test)

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.passed.append(test)

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.passed.append(test)


code, result = 1, None
try:
    loader = unittest.TestLoader()
    if fname:
        sys.path[0] = os.path.dirname(os.path.abspath(fname))
        mod = importlib.import_module(os.path.basename(fname)[:-3])
        suite = loader.loadTestsFromModule(mod)
    else:
        sys.path[0] = os.getcwd()
        suite = loader.discover("tests")
    result = unittest.TextTestRunner(verbosity=0, resultclass=Result).run(suite)
    if not result.wasSuccessful():
        code = 1
    elif result.testsRun == 0 and not result.skipped:
        code = 5
    else:
        code = 0
except BaseException as e:  # noqa: BLE001 - import error of a --file module, missing tests/ ...
    import traceback
    traceback.print_exc()
    code = 1

k = n = 0
for m, cnt in expect.items():
    got = 0
    if result is not None:
        got = sum(1 for t in result.passed if t.id().split(".")[0] == m)
    k += min(got, cnt)
    n += cnt
if suite_item:
    n += 1
    k += code == 0
sys.stdout.flush()
sys.stderr.flush()
print(f"ITEMS {k}/{n}", flush=True)
sys.exit(code)
