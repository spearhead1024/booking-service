import pytest

from app.domain import DateRange
from app.exceptions import InvalidDateRangeError
from tests.overlap_cases import ALL_CASES, EXISTING, OverlapCase, day

EXISTING_RANGE = DateRange(day(EXISTING[0]), day(EXISTING[1]))


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda c: c.id)
def test_overlap_matches_spec(case: OverlapCase) -> None:
    new_range = DateRange(day(case.start), day(case.end))

    assert new_range.overlaps(EXISTING_RANGE) is case.overlaps


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda c: c.id)
def test_overlap_is_symmetric(case: OverlapCase) -> None:
    new_range = DateRange(day(case.start), day(case.end))

    assert new_range.overlaps(EXISTING_RANGE) == EXISTING_RANGE.overlaps(new_range)


@pytest.mark.parametrize(("start", "end"), [(5, 5), (6, 5)], ids=["same-day", "reversed"])
def test_rejects_start_not_before_end(start: int, end: int) -> None:
    with pytest.raises(InvalidDateRangeError):
        DateRange(day(start), day(end))
