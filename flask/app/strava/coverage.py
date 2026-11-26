"""Infrastructure-independent interval calculations for synchronisation."""


def missing_intervals(start, end, completed):
    """Return uncovered half-open intervals, newest first."""
    if start >= end:
        return []
    cursor = start
    gaps = []
    for lower, upper in sorted(completed):
        if upper <= cursor or lower >= end:
            continue
        if lower > cursor:
            gaps.append((cursor, lower))
        cursor = max(cursor, upper)
        if cursor >= end:
            break
    if cursor < end:
        gaps.append((cursor, end))
    return list(reversed(gaps))
