from dataclasses import dataclass, replace
from datetime import date

DECAY_RATE = 0.8
GRADUATION_THRESHOLD = 45  # minutes/day


@dataclass
class CocoonProfile:
    user_id: str
    start_minutes: int
    current_week: int
    start_date: date


def calculate_this_weeks_cap(profile: CocoonProfile) -> int:
    return int(profile.start_minutes * (DECAY_RATE ** profile.current_week))


def should_graduate(profile: CocoonProfile) -> bool:
    return calculate_this_weeks_cap(profile) <= GRADUATION_THRESHOLD


def advance_week(profile: CocoonProfile) -> CocoonProfile:
    return replace(profile, current_week=profile.current_week + 1)
