"""UART GPS reader wrapping micropyGPS for the BN-220 module."""

import sys
from machine import UART, Pin
from micropyGPS import MicropyGPS
import math

# Days per month (non-leap / leap year index 1 for Feb)
_DAYS_IN_MONTH = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _is_leap_year(y):
    return (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0)


def _days_in_month(month, year):
    if month == 2 and _is_leap_year(year):
        return 29
    return _DAYS_IN_MONTH[month - 1]


class GPSReader:
    __slots__ = ('_uart', '_gps', '_has_ever_had_fix',
                 '_lat_mins', '_lat_dec', '_lon_mins', '_lon_dec',
                 '_cached_mh_lat', '_cached_mh_lon', '_cached_mh',
                 '_cached_utm_lat', '_cached_utm_lon', '_cached_utm')

    def __init__(self, tx_pin=1, rx_pin=2, baudrate=9600):
        self._uart = UART(1, baudrate=baudrate, tx=Pin(tx_pin), rx=Pin(rx_pin), rxbuf=512)
        self._gps = MicropyGPS()
        self._has_ever_had_fix = False

        # Cached decimal coordinates
        self._lat_mins = None
        self._lat_dec = 0.0
        self._lon_mins = None
        self._lon_dec = 0.0

        # Cached maidenhead
        self._cached_mh_lat = None
        self._cached_mh_lon = None
        self._cached_mh = "------"

        # Cached UTM
        self._cached_utm_lat = None
        self._cached_utm_lon = None
        self._cached_utm = "-- --E --N"

    def feed(self):
        """Drain UART buffer, feed bytes to the parser, and echo to USB."""
        n = self._uart.any()
        if n:
            buf = self._uart.read(n)
            if buf:
                for b in buf:
                    self._gps.update(b)
                try:
                    sys.stdout.buffer.write(buf)
                except:
                    pass
        if not self._has_ever_had_fix and self._gps.valid:
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

    @property
    def utc_year(self):
        return 2000 + self._gps.date[2]

    @property
    def utc_month(self):
        return self._gps.date[1]

    @property
    def utc_day(self):
        return self._gps.date[0]

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
        """Return latitude in decimal degrees (positive N, negative S). Cached."""
        lat = self._gps._latitude
        if lat[1] != self._lat_mins:
            self._lat_mins = lat[1]
            dec = lat[0] + lat[1] / 60.0
            if lat[2] == 'S':
                dec = -dec
            self._lat_dec = dec
        return self._lat_dec

    @property
    def longitude_decimal(self):
        """Return longitude in decimal degrees (positive E, negative W). Cached."""
        lon = self._gps._longitude
        if lon[1] != self._lon_mins:
            self._lon_mins = lon[1]
            dec = lon[0] + lon[1] / 60.0
            if lon[2] == 'W':
                dec = -dec
            self._lon_dec = dec
        return self._lon_dec

    def lat_str(self):
        """Formatted latitude string like '40.712800 N'."""
        return "{:.6f} {}".format(abs(self.latitude_decimal), self._gps._latitude[2])

    def lon_str(self):
        """Formatted longitude string like '74.006000 W'."""
        return "{:.6f} {}".format(abs(self.longitude_decimal), self._gps._longitude[2])

    # --- Maidenhead grid locator ---

    @property
    def maidenhead(self):
        """Compute 6-character Maidenhead grid locator from current position. Cached."""
        if not self._has_ever_had_fix:
            return "------"

        lat = self.latitude_decimal
        lon = self.longitude_decimal
        if lat == self._cached_mh_lat and lon == self._cached_mh_lon:
            return self._cached_mh

        lon_adj = lon + 180.0
        lat_adj = lat + 90.0

        # Field (20x10 degrees)
        lon_field = int(lon_adj / 20)
        lat_field = int(lat_adj / 10)
        # Square (2x1 degrees)
        lon_sq = int((lon_adj - lon_field * 20) / 2)
        lat_sq = int(lat_adj - lat_field * 10)
        # Subsquare (5min x 2.5min)
        lon_sub = int((lon_adj - lon_field * 20 - lon_sq * 2) * 12)
        lat_sub = int((lat_adj - lat_field * 10 - lat_sq) * 24)

        result = "{}{}{}{}{}{}".format(
            chr(65 + lon_field),
            chr(65 + lat_field),
            chr(48 + lon_sq),
            chr(48 + lat_sq),
            chr(97 + lon_sub),
            chr(97 + lat_sub),
        )
        self._cached_mh_lat = lat
        self._cached_mh_lon = lon
        self._cached_mh = result
        return result

    # --- UTM coordinates ---

    @property
    def utm(self):
        """Compute UTM coordinates from current position (WGS84). Cached."""
        if not self._has_ever_had_fix:
            return "-- --E --N"

        lat = self.latitude_decimal
        lon = self.longitude_decimal
        if lat == self._cached_utm_lat and lon == self._cached_utm_lon:
            return self._cached_utm

        _sin = math.sin
        _cos = math.cos
        _tan = math.tan
        _sqrt = math.sqrt
        _pi = math.pi

        a = 6378137.0
        f = 1.0 / 298.257223563
        e2 = 2 * f - f * f
        ep2 = e2 / (1 - e2)
        k0 = 0.9996

        zone = int((lon + 180) / 6) + 1
        lon0 = (zone - 1) * 6 - 180 + 3

        lat_r = lat * _pi / 180
        dlon = (lon - lon0) * _pi / 180

        sin_lat = _sin(lat_r)
        cos_lat = _cos(lat_r)
        tan_lat = _tan(lat_r)

        N = a / _sqrt(1 - e2 * sin_lat * sin_lat)
        T = tan_lat * tan_lat
        C = ep2 * cos_lat * cos_lat
        A = cos_lat * dlon

        M = a * ((1 - e2 / 4 - 3 * e2 * e2 / 64) * lat_r
                 - (3 * e2 / 8 + 3 * e2 * e2 / 32) * _sin(2 * lat_r)
                 + (15 * e2 * e2 / 256) * _sin(4 * lat_r))

        A2 = A * A
        A3 = A2 * A
        A4 = A3 * A
        A5 = A4 * A
        A6 = A5 * A

        easting = k0 * N * (A + (1 - T + C) * A3 / 6
                             + (5 - 18 * T + T * T + 72 * C - 58 * ep2) * A5 / 120) + 500000
        northing = k0 * (M + N * tan_lat * (A2 / 2
                         + (5 - T + 9 * C + 4 * C * C) * A4 / 24
                         + (61 - 58 * T + T * T + 600 * C - 330 * ep2) * A6 / 720))
        if lat < 0:
            northing += 10000000

        bands = 'CDEFGHJKLMNPQRSTUVWX'
        if -80 <= lat <= 84:
            band = bands[int((lat + 80) / 8)]
        else:
            band = 'X' if lat > 84 else 'C'

        result = "{:d}{} {:06d}E {:07d}N".format(zone, band, int(easting), int(northing))
        self._cached_utm_lat = lat
        self._cached_utm_lon = lon
        self._cached_utm = result
        return result
