"""UART GPS reader wrapping micropyGPS for the BN-220 module."""

from machine import UART, Pin
from micropyGPS import MicropyGPS
from math import floor

# Days per month (non-leap / leap year index 1 for Feb)
_DAYS_IN_MONTH = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _is_leap_year(y):
    return (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0)


def _days_in_month(month, year):
    if month == 2 and _is_leap_year(year):
        return 29
    return _DAYS_IN_MONTH[month - 1]


class GPSReader:
    def __init__(self, tx_pin=1, rx_pin=2, baudrate=9600):
        self._uart = UART(1, baudrate=baudrate, tx=Pin(tx_pin), rx=Pin(rx_pin), rxbuf=512)
        self._gps = MicropyGPS()
        self._has_ever_had_fix = False

    def feed(self):
        """Drain UART buffer and feed characters to the parser."""
        while self._uart.any():
            ch = self._uart.read(1)
            if ch:
                self._gps.update(chr(ch[0]))
        if self._gps.valid:
            self._has_ever_had_fix = True

    # --- Time ---

    @property
    def hours(self):
        return self._gps.timestamp[0]

    @property
    def minutes(self):
        return self._gps.timestamp[1]

    @property
    def seconds(self):
        return int(self._gps.timestamp[2])

    @property
    def time_is_valid(self):
        """True if we have ever received a valid fix (time keeps running)."""
        return self._has_ever_had_fix

    def time_str(self, tz_offset=0):
        """Return HH:MM:SS string adjusted for timezone offset."""
        h = (self.hours + tz_offset) % 24
        return "{:02d}:{:02d}:{:02d}".format(h, self.minutes, self.seconds)

    # --- Fix info ---

    @property
    def has_fix(self):
        return self._gps.valid

    @property
    def has_ever_had_fix(self):
        return self._has_ever_had_fix

    @property
    def fix_type(self):
        return self._gps.fix_type

    @property
    def fix_type_str(self):
        ft = self._gps.fix_type
        if ft == 3:
            return "3D"
        elif ft == 2:
            return "2D"
        return "None"

    @property
    def satellites_in_use(self):
        return self._gps.satellites_in_use

    @property
    def satellites_in_view(self):
        return self._gps.satellites_in_view

    # --- Date ---

    def date_str(self, tz_offset=0):
        """Return YYYY-MM-DD adjusted for timezone offset (handles midnight crossing)."""
        d, m, y = self._gps.date  # (day, month, 2-digit year)
        if d == 0 and m == 0 and y == 0:
            return "----.--.--"
        year = 2000 + y
        utc_hour = self._gps.timestamp[0]
        local_hour = utc_hour + tz_offset

        if local_hour < 0:
            # Previous day
            d -= 1
            if d < 1:
                m -= 1
                if m < 1:
                    m = 12
                    year -= 1
                d = _days_in_month(m, year)
        elif local_hour >= 24:
            # Next day
            d += 1
            if d > _days_in_month(m, year):
                d = 1
                m += 1
                if m > 12:
                    m = 1
                    year += 1

        return "{:04d}-{:02d}-{:02d}".format(year, m, d)

    # --- Position ---

    @property
    def latitude_decimal(self):
        """Return latitude in decimal degrees (positive N, negative S)."""
        lat = self._gps._latitude
        dec = lat[0] + lat[1] / 60.0
        if lat[2] == 'S':
            dec = -dec
        return dec

    @property
    def longitude_decimal(self):
        """Return longitude in decimal degrees (positive E, negative W)."""
        lon = self._gps._longitude
        dec = lon[0] + lon[1] / 60.0
        if lon[2] == 'W':
            dec = -dec
        return dec

    def lat_str(self):
        """Formatted latitude string like '40.7128 N'."""
        lat = self._gps._latitude
        dec = lat[0] + lat[1] / 60.0
        return "{:.4f} {}".format(dec, lat[2])

    def lon_str(self):
        """Formatted longitude string like '74.0060 W'."""
        lon = self._gps._longitude
        dec = lon[0] + lon[1] / 60.0
        return "{:.4f} {}".format(dec, lon[2])

    # --- Maidenhead grid locator ---

    @property
    def maidenhead(self):
        """Compute 6-character Maidenhead grid locator from current position."""
        if not self._has_ever_had_fix:
            return "------"
        lon = self.longitude_decimal + 180.0
        lat = self.latitude_decimal + 90.0

        # Field (20x10 degrees)
        lon_field = int(lon / 20)
        lat_field = int(lat / 10)
        # Square (2x1 degrees)
        lon_sq = int((lon - lon_field * 20) / 2)
        lat_sq = int(lat - lat_field * 10)
        # Subsquare (5min x 2.5min)
        lon_sub = int((lon - lon_field * 20 - lon_sq * 2) * 12)
        lat_sub = int((lat - lat_field * 10 - lat_sq) * 24)

        return "{}{}{}{}{}{}".format(
            chr(65 + lon_field),
            chr(65 + lat_field),
            chr(48 + lon_sq),
            chr(48 + lat_sq),
            chr(97 + lon_sub),
            chr(97 + lat_sub),
        )
