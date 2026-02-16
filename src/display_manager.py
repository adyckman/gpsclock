"""Display layout and partial-update rendering for the GPS clock.

320x170 landscape (rotation=1), ST7789 driver with fixed_v01 font.

Zone A (top): Local time + TZ abbreviation, UTC time below
Zone B (bottom): Date, satellite info, fix status, coordinates, grid square
"""

import st7789
import fixed_v01_8 as font

# Colors (RGB565)
WHITE = st7789.color565(255, 255, 255)
BLACK = st7789.color565(0, 0, 0)
GREEN = st7789.color565(0, 255, 0)
RED = st7789.color565(255, 0, 0)
CYAN = st7789.color565(0, 255, 255)
YELLOW = st7789.color565(255, 255, 0)
ORANGE = st7789.color565(255, 165, 0)
GRAY = st7789.color565(128, 128, 128)

# Screen dimensions
SCREEN_W = 320
SCREEN_H = 170

# Character metrics (most chars 6px wide, HEIGHT 9px)
CHAR_W = 6

# Zone A: local time + TZ, then UTC time
TIME_X = (SCREEN_W - 8 * CHAR_W) // 2   # "HH:MM:SS" centered
TIME_Y = 37
TZ_X = TIME_X + 8 * CHAR_W + 4          # abbreviation right of time
TZ_Y = TIME_Y                           # same line, same font
UTC_X = (SCREEN_W - 12 * CHAR_W) // 2   # "UTC HH:MM:SS" centered
UTC_Y = 54

# Separator
SEP_Y = 71

# Zone B: GPS info rows (~53 chars per line at 6px)
ROW1_Y = 80
ROW2_Y = 97

# Status message area
STATUS_X = 8
STATUS_Y = 114
STATUS_CLEAR_W = 180


class DisplayManager:
    def __init__(self, tft):
        self._tft = tft
        self._cache = {}
        self._first_draw = True

    def init_screen(self):
        """Clear screen and draw static elements."""
        self._tft.fill(BLACK)
        self._tft.hline(0, SEP_Y, SCREEN_W, GRAY)
        self._first_draw = True
        self._cache.clear()

    def _draw_text_if_changed(self, key, text, x, y, color, clear_width=0):
        """Only redraw text if it has changed since last call with this key."""
        prev = self._cache.get(key)
        if prev == (text, color) and not self._first_draw:
            return
        self._cache[key] = (text, color)
        if clear_width > 0:
            self._tft.fill_rect(x, y, clear_width, font.HEIGHT, BLACK)
        if text:
            self._tft.write(font, text, x, y, color, BLACK)

    def update(self, gps, tz):
        """Refresh all display regions with current GPS and timezone data."""
        self._update_time(gps, tz)
        self._update_gps_info(gps, tz)
        self._first_draw = False

    def _update_time(self, gps, tz):
        """Draw local time, TZ abbreviation, and UTC time."""
        if gps.time_is_valid:
            local_text = gps.time_str(tz.offset)
            utc_text = "UTC " + gps.time_str(0)
            time_color = WHITE
            utc_color = GRAY
        else:
            local_text = "--:--:--"
            utc_text = "UTC --:--:--"
            time_color = GRAY
            utc_color = GRAY

        self._draw_text_if_changed(
            "time", local_text, TIME_X, TIME_Y, time_color, clear_width=54)
        self._draw_text_if_changed(
            "tz", tz.abbreviation, TZ_X, TZ_Y, CYAN, clear_width=30)
        self._draw_text_if_changed(
            "utc", utc_text, UTC_X, UTC_Y, utc_color, clear_width=78)

    def _update_gps_info(self, gps, tz):
        """Draw GPS info in Zone B: date, satellites, fix, coords, grid."""
        if not gps.has_ever_had_fix:
            self._draw_text_if_changed(
                "status", "Acquiring satellites...",
                STATUS_X, STATUS_Y, ORANGE, clear_width=STATUS_CLEAR_W)
            # Clear data rows
            for key in ("date", "sats", "fix", "lat", "lon", "grid"):
                self._cache[key] = ("", BLACK)
            return

        # Clear acquiring message when we first get a fix
        self._draw_text_if_changed(
            "status", "", STATUS_X, STATUS_Y, BLACK, clear_width=STATUS_CLEAR_W)

        # Row 1: Date | Sat:U/V | Fix:type
        date_text = gps.date_str(tz.offset)
        self._draw_text_if_changed(
            "date", date_text, 8, ROW1_Y, YELLOW, clear_width=66)

        sat_text = "Sat:{}/{}".format(gps.satellites_in_use, gps.satellites_in_view)
        self._draw_text_if_changed(
            "sats", sat_text, 96, ROW1_Y, WHITE, clear_width=60)

        fix_text = "Fix:{}".format(gps.fix_type_str)
        fix_color = GREEN if gps.has_fix else RED
        self._draw_text_if_changed(
            "fix", fix_text, 178, ROW1_Y, fix_color, clear_width=48)

        # Row 2: Lat | Lon | Grid
        if gps.has_fix:
            lat_text = gps.lat_str()
            lon_text = gps.lon_str()
            grid_text = gps.maidenhead
            coord_color = WHITE
        else:
            lat_text = "-- N"
            lon_text = "-- W"
            grid_text = "------"
            coord_color = GRAY

        self._draw_text_if_changed(
            "lat", lat_text, 8, ROW2_Y, coord_color, clear_width=66)
        self._draw_text_if_changed(
            "lon", lon_text, 96, ROW2_Y, coord_color, clear_width=66)
        self._draw_text_if_changed(
            "grid", grid_text, 184, ROW2_Y, CYAN, clear_width=42)

        # Signal lost warning
        if not gps.has_fix:
            self._draw_text_if_changed(
                "status", "Signal lost",
                STATUS_X, STATUS_Y, RED, clear_width=STATUS_CLEAR_W)
