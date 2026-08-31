from datetime import datetime, timedelta

from assistant.tools.builtin import get_current_time


def test_get_current_time():
    result = get_current_time.invoke(
        {
            "timezone": "Asia/Shanghai",
        }
    )

    parsed_time = datetime.fromisoformat(result)

    assert parsed_time.utcoffset() == timedelta(hours=8)


def test_get_current_time_with_invalid_timezone():
    result = get_current_time.invoke(
        {
            "timezone": "Invalid/Timezone",
        }
    )

    assert result == "Unknown timezone: Invalid/Timezone"