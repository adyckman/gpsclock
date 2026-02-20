"""US timezone definitions with DST support and button cycling on GPIO14."""

from machine import Pin
import time

# US timezone table: (name, std_abbr, std_offset, dst_abbr, dst_offset, observes_dst)
_ZONES = (
    ("US Eastern",  "EST", -5, "EDT", -4, True),
    ("US Central",  "CST", -6, "CDT", -5, True),
    ("US Mountain", "MST", -7, "MDT", -6, True),
    ("Arizona",     "MST", -7, "MST", -7, False),
    ("US Pacific",  "PST", -8, "PDT", -7, True),
    ("Alaska",      "AKST", -9, "AKDT", -8, True),
    ("Hawaii",      "HST", -10, "HST", -10, False),
)

_DEBOUNCE_MS = 250
_LONG_PRESS_MS = 1000


def _day_of_week(year, month, day):
    """Return day of week (0=Sunday, 1=Monday, ..., 6=Saturday).

    Uses Tomohiko Sakamoto's algorithm.
    """
    t = (0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4)
    if month < 3:
        year -= 1
    return (year + year // 4 - year // 100 + year // 400 + t[month - 1] + day) % 7


def _nth_sunday(year, month, n):
    """Return the day-of-month of the nth Sunday in the given month."""
    # Find first Sunday
    dow = _day_of_week(year, month, 1)  # day of week for the 1st
    first_sunday = 1 + (7 - dow) % 7
    return first_sunday + 7 * (n - 1)


def _is_dst(utc_year, utc_month, utc_day, utc_hour, std_offset):
    """Determine if DST is active for the given UTC time and standard offset.

    US DST: starts 2nd Sunday of March at 2:00 AM local (= 2-std_offset UTC),
            ends 1st Sunday of November at 2:00 AM local (= 2-dst_offset UTC).
    """
    dst_start_day = _nth_sunday(utc_year, 3, 2)   # 2nd Sunday in March
    dst_end_day = _nth_sunday(utc_year, 11, 1)     # 1st Sunday in November

    # Transition times in UTC hours
    # Spring forward: 2:00 AM standard time = (2 - std_offset) UTC
    spring_utc_hour = 2 - std_offset
    # Fall back: 2:00 AM daylight time = (2 - (std_offset + 1)) UTC
    fall_utc_hour = 2 - (std_offset + 1)

    # Encode as comparable value: month * 100000 + day * 1000 + hour
    now = utc_month * 100000 + utc_day * 1000 + utc_hour
    start = 3 * 100000 + dst_start_day * 1000 + spring_utc_hour
    end = 11 * 100000 + dst_end_day * 1000 + fall_utc_hour

    return start <= now < end


class TimezoneManager:
    def __init__(self, button_pin=14):
        self._index = 0
        self._button = Pin(button_pin, Pin.IN, Pin.PULL_UP)
        self._last_release = 0
        self._dst_active = False
        self._manually_set = False
        self._auto_detected = False
        self._button_down = False
        self._press_start = 0
        self._last_dst_hour = -1
        self._last_dst_day = -1

    def check_button(self):
        """Poll button; returns 0 (no action), 1 (short press), or 2 (long press)."""
        pressed = self._button.value() == 0
        now = time.ticks_ms()

        if pressed and not self._button_down:
            # Button just pressed — ignore if too soon after last release (bounce)
            if time.ticks_diff(now, self._last_release) > _DEBOUNCE_MS:
                self._button_down = True
                self._press_start = now
        elif not pressed and self._button_down:
            # Button just released
            self._button_down = False
            self._last_release = now
            duration = time.ticks_diff(now, self._press_start)
            if duration >= _LONG_PRESS_MS:
                self._last_dst_hour = -1
                return 2
            self._index = (self._index + 1) % len(_ZONES)
            self._manually_set = True
            self._last_dst_hour = -1
            return 1

        return 0

    def set_from_location(self, lat, lon, force=False):
        """Auto-detect timezone from GPS coordinates.

        Skips if the user has already pressed the timezone button or
        auto-detection has already run, unless force=True (long press).
        """
        if not force and (self._manually_set or self._auto_detected):
            return False
        try:
            from tz_grid import lookup
            idx = lookup(lat, lon)
            if 0 <= idx < len(_ZONES):
                self._index = idx
                self._auto_detected = True
                self._last_dst_hour = -1
                return True
        except Exception:
            pass
        return False

    def update_dst(self, utc_year, utc_month, utc_day, utc_hour):
        """Update DST state based on current UTC time. Cached until hour/day changes."""
        if utc_hour == self._last_dst_hour and utc_day == self._last_dst_day:
            return
        self._last_dst_hour = utc_hour
        self._last_dst_day = utc_day
        zone = _ZONES[self._index]
        if zone[5]:  # observes DST
            self._dst_active = _is_dst(utc_year, utc_month, utc_day, utc_hour, zone[2])
        else:
            self._dst_active = False

    @property
    def offset(self):
        zone = _ZONES[self._index]
        return zone[4] if self._dst_active else zone[2]

    @property
    def name(self):
        return _ZONES[self._index][0]

    @property
    def abbreviation(self):
        zone = _ZONES[self._index]
        return zone[3] if self._dst_active else zone[1]

    @property
    def label(self):
        off = self.offset
        sign = "+" if off >= 0 else ""
        return "{} (UTC{}{})".format(self.name, sign, off)
