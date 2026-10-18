"""Reference solutions for tasks_xxhard.py (files under xxhard/<id>/ref/ overlay the seed)."""
from tasks_xxhard import tree

R = {tid: tree(tid, "ref") for tid in ["y_library", "y_tzreport", "y_ledger_split", "y_timesheet", "y_perf_report"]}
R["y_ledger_split"]["!"] = "rm ledger.py"
