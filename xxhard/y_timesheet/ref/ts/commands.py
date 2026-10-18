import re
from datetime import date

from ts.durations import format_minutes, parse_duration
from ts.errors import ConfigError, TsError, UsageError
from ts.store import Entry, append_entry, load_entries

_PROJECT = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def check_date(text):
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        raise UsageError(f"invalid date: {text}") from None


def check_project(text):
    if not _PROJECT.match(text):
        raise UsageError(f"invalid project: {text}")
    return text


def sorted_entries(ctx, project=None):
    entries = load_entries(ctx.data_path)
    if project:
        entries = [e for e in entries if e.project == project]
    return sorted(entries, key=lambda e: e.date)     # stable: file order within a day


def cmd_add(ctx, args):
    entry = Entry(check_date(args.date), check_project(args.project), parse_duration(args.duration), " ".join(args.note))
    append_entry(ctx.data_path, entry)
    print(f"added: {entry.date} {entry.project} {format_minutes(entry.minutes)}")


def cmd_list(ctx, args):
    entries = sorted_entries(ctx, args.project)
    for e in entries:
        print(f"{e.date}  {e.project}  {format_minutes(e.minutes)}  {e.note}".rstrip())
    if not entries:
        print("no entries")


def cmd_total(ctx, args):
    entries = sorted_entries(ctx, args.project)
    if not entries:
        print("no entries")
        return
    totals = {}
    for e in entries:
        totals[e.project] = totals.get(e.project, 0) + e.minutes
    for project in sorted(totals):
        print(f"{project}  {format_minutes(totals[project])}")
    print(f"TOTAL  {format_minutes(sum(totals.values()))}")


def cmd_invoice(ctx, args):
    project = check_project(args.project)
    if not _MONTH.match(args.month):
        raise UsageError(f"invalid month: {args.month}")
    sec = ctx.config.section(f"project.{project}")
    if "rate" not in sec:
        raise TsError(f"no rate for project: {project}")
    if not re.fullmatch(r"\d+", sec["rate"]):
        raise ConfigError(f"bad rate for project: {project}")
    rate = int(sec["rate"])
    step = ctx.config.get("round_to", "1", section="invoice")
    if not re.fullmatch(r"\d+", step) or int(step) < 1:
        raise ConfigError("bad invoice.round_to")
    step = int(step)
    entries = [e for e in sorted_entries(ctx, project) if e.date.startswith(args.month + "-")]
    print(f"Invoice: {sec.get('name', project)} ({project}) {args.month}")
    total_min = total_yen = 0
    for e in entries:
        billed = -(-e.minutes // step) * step
        yen = (2 * billed * rate + 60) // 120
        total_min += billed
        total_yen += yen
        print(f"{e.date}  {format_minutes(billed)}  {yen:,}  {e.note}".rstrip())
    print(f"Total: {format_minutes(total_min)}  {total_yen:,}")
