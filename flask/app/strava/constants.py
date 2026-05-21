# Earliest epoch timestamp we'll accept for activity queries (2020-01-01)
EARLIEST_EPOCH = 1577836800

# Default days of history to fetch from Strava when no prior sync exists
DEFAULT_SYNC_HISTORY_DAYS = 60

# Maximum window for activity list queries from the local DB (frontend display)
# NOTE: routes.py used 2800 and utils.py used 60 under the same name DEFAULT_HISTORY_DAYS.
# These serve different purposes and are now named explicitly to avoid confusion.
DEFAULT_ACTIVITY_QUERY_DAYS = 2800

# How far back to look when performing an incremental sync
SYNCH_WINDOW_DAYS = 30

# Coordinate sampling for map display
COORDINATE_SAMPLE_RATE = 5
MIN_COORDINATE_POINTS = 50
MAX_COORDINATE_POINTS = 300
