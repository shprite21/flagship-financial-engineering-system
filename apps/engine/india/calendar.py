"""Explicit, bounded NSE cash calendar; unknown dates fail closed for live tickets."""
from datetime import date, datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
HOLIDAYS = {
    '2026-01-15', '2026-01-26', '2026-03-03', '2026-03-26', '2026-03-31',
    '2026-04-03', '2026-04-14', '2026-05-01', '2026-05-28', '2026-06-26',
    '2026-09-14', '2026-10-02', '2026-10-20', '2026-11-10', '2026-11-24', '2026-12-25',
}
SOURCE = 'https://www.nseindia.com/resources/exchange-communication-holidays'


def session(day):
    day = date.fromisoformat(str(day)[:10])
    if day.year != 2026:
        raise ValueError('NSE calendar year unverified')
    return day.weekday() < 5 and day.isoformat() not in HOLIDAYS


def prior_session(day):
    day = date.fromisoformat(str(day)[:10])-timedelta(days=1)
    while not session(day):
        day -= timedelta(days=1)
    return day.isoformat()


def entry_window(now):
    now = now.astimezone(IST)
    return session(now.date()) and (9, 15) <= (now.hour, now.minute) < (9, 20)


def target_week():
    return [{'date': f'2026-10-{day}', 'open': session(f'2026-10-{day}'),
             'reason': 'Dussehra' if day == 20 else 'Scheduled normal cash session'} for day in range(19,24)]
