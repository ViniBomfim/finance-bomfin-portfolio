import calendar
from datetime import date


def date_in_month(year: int, month: int, preferred_day: int) -> date:
    _, last = calendar.monthrange(year, month)
    day = min(max(preferred_day, 1), last)
    return date(year, month, day)
