from datetime import datetime, time


def normalize_range(value, fallback):
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return value[0], value[1]
    return fallback


def bounds(start_date, end_date):
    """Return naive server-local bounds compatible with Pyrogram datetimes.

    Pyrogram 2.x converts Telegram timestamps with datetime.fromtimestamp() and
    converts offset dates back with datetime.timestamp(). Both use the host's
    local timezone for naive datetime values. Streamlit's date picker has no
    timezone component, so selected calendar days are intentionally interpreted
    in the server's local timezone as well.
    """
    return (
        datetime.combine(start_date, time.min),
        datetime.combine(end_date, time.max),
    )
