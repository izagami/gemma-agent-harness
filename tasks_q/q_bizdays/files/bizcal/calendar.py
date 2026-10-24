"""The office calendar: Saturdays, Sundays and the days listed in data/holidays.txt are closed."""
import datetime as dt
import os

HOLIDAYS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "holidays.txt")


def load_holidays(path=HOLIDAYS_FILE):
    """{date: name} from lines `YYYY-MM-DD name`; `#` starts a comment, blank lines are ignored."""
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            day, _, name = line.partition(" ")
            out[dt.date.fromisoformat(day)] = name.strip()
    return out


class Calendar:
    def __init__(self, holidays=None):
        self.all = load_holidays() if holidays is None else dict(holidays)
        self._by_year = {}

    def holidays(self, year):
        """The holidays of one year (a set of dates)."""
        if year not in self._by_year:
            self._by_year[year] = {d for d in self.all if d.year == year}
        return self._by_year[year]

    def is_business_day(self, day, holidays=None):
        """Monday to Friday and not a holiday. `holidays` may pass a pre-computed set for speed."""
        hs = self.holidays(day.year) if holidays is None else holidays
        return day.weekday() < 5 and day not in hs
