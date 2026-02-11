"""Display layout and partial-update rendering for the GPS clock.

320x170 landscape (rotation=1), ST7789 driver with built-in bitmap fonts.

Zone A (top): Local time (16x16) + TZ abbreviation, UTC time below
Zone B (bottom): Date, satellite info, fix status, coordinates, grid square
"""

import st7789
import vga1_16x16 as font_time
import vga1_8x8 as font_narrow

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

# Zone A: local time + TZ, then UTC time
TIME_X = 80                 # "HH:MM:SS" 8 chars * 16px = 128px
TIME_Y = 24
TZ_X = TIME_X + 128 + 6    # abbreviation right of time
TZ_Y = TIME_Y + 16 - 8     # bottom-aligned with time text
UTC_X = (SCREEN_W - 96) // 2  # "UTC HH:MM:SS" 12 chars * 8px = 96px
UTC_Y = 48

# Separator
SEP_Y = 64

# Zone B: GPS info rows (8x8 font, 40 chars per line)
ROW1_Y = 78
ROW2_Y = 94

# Status message area
STATUS_X = 8
STATUS_Y = 114
STATUS_CLEAR_W = 240


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

    def _draw_text_if_changed(self, key, text, x, y, font, color, clear_width=0):
        """Only redraw text if it has changed since last call with this key."""
        prev = self._cache.get(key)
        if prev == (text, color) and not self._first_draw:
            return
        self._cache[key] = (text, color)
        if clear_width > 0:
            self._tft.fill_rect(x, y, clear_width, font.HEIGHT, BLACK)
        if text:
            self._tft.text(font, text, x, y, color, BLACK)

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
            "time", local_text, TIME_X, TIME_Y, font_time, time_color, clear_width=128)
        self._draw_text_if_changed(
            "tz", tz.abbreviation, TZ_X, TZ_Y, font_narrow, CYAN, clear_width=32)
        self._draw_text_if_changed(
            "utc", utc_text, UTC_X, UTC_Y, font_narrow, utc_color, clear_width=96)

    def _update_gps_info(self, gps, tz):
        """Draw GPS info in Zone B: date, satellites, fix, coords, grid."""
        if not gps.has_ever_had_fix:
            self._draw_text_if_changed(
                "status", "Acquiring satellites...",
                STATUS_X, STATUS_Y, font_narrow, ORANGE, clear_width=STATUS_CLEAR_W)
            # Clear data rows
            for key in ("date", "sats", "fix", "lat", "lon", "grid"):
                self._cache[key] = ("", BLACK)
            return

        # Clear acquiring message when we first get a fix
        self._draw_text_if_changed(
            "status", "", STATUS_X, STATUS_Y, font_narrow, BLACK, clear_width=STATUS_CLEAR_W)

        # Row 1: Date | Sat:U/V | Fix:type
        date_text = gps.date_str(tz.offset)
        self._draw_text_if_changed(
            "date", date_text, 8, ROW1_Y, font_narrow, YELLOW, clear_width=88)

        sat_text = "Sat:{}/{}".format(gps.satellites_in_use, gps.satellites_in_view)
        self._draw_text_if_changed(
            "sats", sat_text, 120, ROW1_Y, font_narrow, WHITE, clear_width=80)

        fix_text = "Fix:{}".format(gps.fix_type_str)
        fix_color = GREEN if gps.has_fix else RED
        self._draw_text_if_changed(
            "fix", fix_text, 224, ROW1_Y, font_narrow, fix_color, clear_width=64)

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
            "lat", lat_text, 8, ROW2_Y, font_narrow, coord_color, clear_width=88)
        self._draw_text_if_changed(
            "lon", lon_text, 120, ROW2_Y, font_narrow, coord_color, clear_width=88)
        self._draw_text_if_changed(
            "grid", grid_text, 232, ROW2_Y, font_narrow, CYAN, clear_width=56)

        # Signal lost warning
        if not gps.has_fix:
            self._draw_text_if_changed(
                "status", "Signal lost",
                STATUS_X, STATUS_Y, font_narrow, RED, clear_width=STATUS_CLEAR_W)
