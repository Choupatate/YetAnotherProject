"""Pure date-math helpers, no framework dependencies."""

from datetime import date


def age_label(birthdate: date, on_date: date) -> str:
    """Human age phrase for `on_date` relative to `birthdate` (FEATURES.md F3)."""
    if on_date < birthdate:
        return "before you were born"

    days = (on_date - birthdate).days
    years = on_date.year - birthdate.year
    months = on_date.month - birthdate.month
    if on_date.day < birthdate.day:
        months -= 1
    total_months = years * 12 + months

    if total_months < 1:
        return f"{days} day{'' if days == 1 else 's'} old"
    if total_months < 12:
        return f"{total_months} month{'' if total_months == 1 else 's'} old"
    total_years = total_months // 12
    return f"{total_years} year{'' if total_years == 1 else 's'} old"
