"""Overlap scenarios from the specification, shared by unit and API tests.

Days are numbers within one month (see ``day``). The existing reservation occupies days
11-16 inclusive, as in the spec table.

Note on the spec table: its "before, no touch" row marks days 10-12, which share days 11-12
with the existing range and so contradict the stated rule ("if the new range shares even a
single day ... it's an overlap"). The written rule is implemented; the row is covered by
its intent (9-10, ending the day before) plus an explicit test of the literal 10-12 range.
"""

from datetime import date
from typing import NamedTuple


def day(n: int) -> date:
    return date(2030, 1, n)


EXISTING = (11, 16)


class OverlapCase(NamedTuple):
    id: str
    start: int
    end: int
    overlaps: bool


SPEC_TABLE_CASES = [
    OverlapCase("before-no-touch", 9, 10, overlaps=False),
    OverlapCase("fully-inside", 12, 14, overlaps=True),
    OverlapCase("touches-start-boundary", 10, 13, overlaps=True),
    OverlapCase("touches-end-boundary", 15, 17, overlaps=True),
    OverlapCase("fully-contains-existing", 10, 17, overlaps=True),
]

EDGE_CASES = [
    OverlapCase("ends-on-existing-start-day", 9, 11, overlaps=True),
    OverlapCase("starts-on-existing-end-day", 16, 18, overlaps=True),
    OverlapCase("starts-day-after-existing-end", 17, 19, overlaps=False),
    OverlapCase("identical-range", 11, 16, overlaps=True),
    OverlapCase("spec-table-literal-before-row", 10, 12, overlaps=True),
]

ALL_CASES = SPEC_TABLE_CASES + EDGE_CASES
