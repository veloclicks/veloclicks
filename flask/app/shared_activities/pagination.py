"""Parse compatible activity date windows and signed owner-scoped cursors."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from itsdangerous import BadData, URLSafeSerializer


class InvalidPage(ValueError):
    """The request cannot be converted to a valid activity list or page."""


def limit_value(raw: str | None) -> int:
    """Enforce the API's existing page-size bounds."""
    try:
        limit = int(raw)
        if 1 <= limit <= 50:
            return limit
    except (TypeError, ValueError):
        pass
    raise InvalidPage("Limit must be between 1 and 50")


def date_window(years: str, now: datetime) -> tuple[datetime, datetime]:
    """Interpret selected years or the existing rolling 180-day default."""
    if not years:
        return now - timedelta(days=180), now
    try:
        selected = [int(year.strip()) for year in years.split(",")]
        return datetime(min(selected), 1, 1), datetime(max(selected), 12, 31, 23, 59, 59)
    except (ValueError, TypeError) as error:
        raise InvalidPage("Invalid years parameter") from error


@dataclass(frozen=True)
class ActivityCursor:
    """Encode and decode the deployed cursor format without database dependencies."""

    secret: str
    user_id: int
    years: str

    def _signer(self) -> URLSafeSerializer:
        """Use the original namespace to keep older cursors valid."""
        return URLSafeSerializer(self.secret, salt="activity-list-cursor")

    def decode(self, cursor: str) -> tuple[datetime | None, tuple[datetime, int]]:
        """Validate the owner and date selection and restore the page boundary."""
        try:
            scope, window_end, date, activity_id = self._signer().loads(cursor)
            if scope != [self.user_id, self.years]:
                raise ValueError
            end = datetime.fromisoformat(window_end) if not self.years else None
            return end, (datetime.fromisoformat(date), activity_id)
        except (BadData, TypeError, ValueError) as error:
            raise InvalidPage("Invalid activity cursor") from error

    def encode(self, end: datetime, start_date: datetime, activity_id: int) -> str:
        """Sign the last row and the first page's rolling window end."""
        return self._signer().dumps([[self.user_id, self.years], end.isoformat(),
                                     start_date.isoformat(), activity_id])
