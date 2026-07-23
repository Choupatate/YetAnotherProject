"""Pure date-math for FEATURES.md F27 life dates: birthdays and union
anniversaries surfaced quietly on the timeline, plus the almanac's full
year-round listing. No framework dependencies, mirroring dates.py and
storage.py's on_this_day.
"""

from datetime import date


def _is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _matches_today(month_day_date: date, today: date) -> bool:
    """True when `month_day_date`'s month/day matches `today`'s, with the
    same Feb 29 -> Mar 1 non-leap-year makeup rule as storage.on_this_day."""
    if month_day_date.month == today.month and month_day_date.day == today.day:
        return True
    return (
        month_day_date.month == 2 and month_day_date.day == 29
        and today.month == 3 and today.day == 1
        and not _is_leap_year(today.year)
    )


def birthdays_today(all_people: list, today: date = None) -> list:
    """Living people (no `died`) whose `born` month/day matches today,
    oldest first. Someone who has died never gets a birthday banner — a
    quiet, deliberate omission, not an oversight."""
    if today is None:
        today = date.today()
    matches = [
        p for p in all_people
        if p.born and not p.died and p.born.year < today.year and _matches_today(p.born, today)
    ]
    matches.sort(key=lambda p: p.born)
    return matches


def union_anniversaries_today(all_people: list, today: date = None) -> list:
    """Ongoing unions (no `until`) whose `since` month/day matches today,
    one entry per couple (unions are stored symmetrically on both
    partners' records, so naively iterating would double every match) —
    each a `{"person", "partner", "kind", "since"}` dict, oldest first. A
    union that has ended never surfaces here, same reasoning as deaths."""
    if today is None:
        today = date.today()
    by_slug = {p.slug: p for p in all_people}
    seen_pairs = set()
    matches = []
    for p in all_people:
        for u in p.unions:
            if u["until"] or u["since"].year >= today.year:
                continue
            if not _matches_today(u["since"], today):
                continue
            pair = tuple(sorted((p.slug, u["partner"])))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            partner = by_slug.get(u["partner"])
            if partner is None:
                continue
            matches.append({"person": p, "partner": partner, "kind": u["kind"], "since": u["since"]})
    matches.sort(key=lambda m: m["since"])
    return matches


def almanac_entries(all_people: list) -> list:
    """Every recorded life date, in month/day order like a real family
    record book's calendar page — independent of year, unlike the
    timeline's dated entries. One entry per birth, one per death, one per
    union (keyed on its `since` date; an `until` is carried on that same
    entry rather than becoming a second recurring date of its own — this
    page is a record, not something to mark as an anniversary)."""
    by_slug = {p.slug: p for p in all_people}
    entries = []
    for p in all_people:
        if p.born:
            entries.append({"type": "born", "date": p.born, "person": p})
        if p.died:
            entries.append({"type": "died", "date": p.died, "person": p})
    seen_pairs = set()
    for p in all_people:
        for u in p.unions:
            pair = tuple(sorted((p.slug, u["partner"])))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            partner = by_slug.get(u["partner"])
            if partner is None:
                continue
            entries.append({
                "type": "union", "date": u["since"], "person": p, "partner": partner,
                "kind": u["kind"], "until": u["until"],
            })
    entries.sort(key=lambda e: (e["date"].month, e["date"].day, e["date"].year))
    return entries
