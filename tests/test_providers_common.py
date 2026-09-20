import pytest

from club_calendar.http import SourceError
from club_calendar.providers._common import guard_skipped


def test_a_couple_of_skipped_matches_are_fine():
    guard_skipped("Kaynak", skipped=2, kept=0)


def test_skipped_matches_next_to_readable_ones_are_fine():
    guard_skipped("Kaynak", skipped=10, kept=1)


def test_nothing_readable_at_all_is_an_error():
    with pytest.raises(SourceError, match="Kaynak: 3 maçın tarihi okunamadı"):
        guard_skipped("Kaynak", skipped=3, kept=0)
