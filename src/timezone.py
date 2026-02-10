"""US timezone definitions with button cycling on GPIO14."""

from machine import Pin
import time

# US timezone table: (name, abbreviation, UTC offset)
_ZONES = (
    ("US Eastern", "EST", -5),
    ("US Central", "CST", -6),
    ("US Mountain", "MST", -7),
    ("US Pacific", "PST", -8),
    ("Alaska", "AKST", -9),
    ("Hawaii", "HST", -10),
)

_DEBOUNCE_MS = 250


class TimezoneManager:
    def __init__(self, button_pin=14):
        self._index = 0
        self._button = Pin(button_pin, Pin.IN, Pin.PULL_UP)
        self._last_press = 0

    def check_button(self):
        """Poll button; returns True if timezone was changed."""
        if self._button.value() == 0:
            now = time.ticks_ms()
            if time.ticks_diff(now, self._last_press) > _DEBOUNCE_MS:
                self._last_press = now
                self._index = (self._index + 1) % len(_ZONES)
                return True
        return False

    @property
    def offset(self):
        return _ZONES[self._index][2]

    @property
    def name(self):
        return _ZONES[self._index][0]

    @property
    def abbreviation(self):
        return _ZONES[self._index][1]

    @property
    def label(self):
        off = self.offset
        sign = "+" if off >= 0 else ""
        return "{} (UTC{}{})".format(self.name, sign, off)
