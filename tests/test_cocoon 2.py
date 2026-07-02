from datetime import date

import pytest

from core.cocoon import (
    CocoonProfile,
    advance_week,
    calculate_this_weeks_cap,
    should_graduate,
)

_START_DATE = date(2026, 4, 25)


def make_profile(start: int = 300, week: int = 0) -> CocoonProfile:
    return CocoonProfile(
        user_id="u1",
        start_minutes=start,
        current_week=week,
        start_date=_START_DATE,
    )


class TestCalculateThisWeeksCap:
    def test_week_zero_returns_start(self):
        assert calculate_this_weeks_cap(make_profile(300, 0)) == 300

    def test_week_one_decays(self):
        assert calculate_this_weeks_cap(make_profile(300, 1)) == 240  # 300 * 0.8

    def test_week_two_decays(self):
        assert calculate_this_weeks_cap(make_profile(300, 2)) == 192  # 300 * 0.64

    def test_returns_int(self):
        assert isinstance(calculate_this_weeks_cap(make_profile(100, 1)), int)

    def test_truncates_float(self):
        # 101 * 0.8 = 80.8 → truncated to 80
        assert calculate_this_weeks_cap(make_profile(101, 1)) == 80


class TestShouldGraduate:
    def test_above_threshold_is_false(self):
        assert not should_graduate(make_profile(300, 0))

    def test_well_above_threshold_is_false(self):
        assert not should_graduate(make_profile(300, 5))

    def test_at_threshold_is_true(self):
        # need start * 0.8^week == 45 exactly
        # 45 * 0.8^0 = 45 → exactly at threshold
        assert should_graduate(make_profile(45, 0))

    def test_below_threshold_is_true(self):
        # 300 * 0.8^10 ≈ 32 → below 45
        assert should_graduate(make_profile(300, 10))

    def test_just_below_threshold_is_true(self):
        # 56 * 0.8^1 = 44 (int) → below 45
        assert should_graduate(make_profile(56, 1))

    def test_just_above_threshold_is_false(self):
        # 58 * 0.8^1 = 46 (int) → above 45
        assert not should_graduate(make_profile(58, 1))


class TestAdvanceWeek:
    def test_increments_week(self):
        assert advance_week(make_profile(300, 3)).current_week == 4

    def test_does_not_mutate_original(self):
        original = make_profile(300, 3)
        advance_week(original)
        assert original.current_week == 3

    def test_preserves_user_id(self):
        p = make_profile(300, 0)
        assert advance_week(p).user_id == p.user_id

    def test_preserves_start_minutes(self):
        p = make_profile(300, 0)
        assert advance_week(p).start_minutes == 300

    def test_preserves_start_date(self):
        p = make_profile(300, 0)
        assert advance_week(p).start_date == _START_DATE

    def test_chained_advance(self):
        p = make_profile(300, 0)
        p = advance_week(advance_week(p))
        assert p.current_week == 2
