"""DHT22 temperature and humidity sensor reader."""

import dht
import time
from machine import Pin

# DHT22 requires minimum 2s between reads
_READ_INTERVAL_MS = 2000


class DHTReader:
    def __init__(self, pin=16):
        self._sensor = dht.DHT22(Pin(pin))
        self._last_read = 0
        self._temp_c = None
        self._humidity = None

    def update(self):
        """Read sensor if enough time has elapsed. Keeps last good reading on error."""
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last_read) < _READ_INTERVAL_MS:
            return
        self._last_read = now
        try:
            self._sensor.measure()
            self._temp_c = self._sensor.temperature()
            self._humidity = self._sensor.humidity()
        except Exception:
            pass

    @property
    def has_reading(self):
        return self._temp_c is not None

    @property
    def temperature_f(self):
        if self._temp_c is None:
            return None
        return self._temp_c * 9.0 / 5.0 + 32.0

    @property
    def humidity(self):
        return self._humidity
