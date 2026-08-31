from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langchain_core.tools import tool


@tool
def get_current_time(timezone: str = "Asia/Shanghai") -> str:
    """Return the current date and time for an IANA timezone."""
    try:
        current_time = datetime.now(ZoneInfo(timezone))
    except ZoneInfoNotFoundError:
        return f"Unknown timezone: {timezone}"

    return current_time.isoformat(timespec="seconds")