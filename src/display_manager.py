"""Display layout and partial-update rendering for the GPS clock.

320x170 landscape (rotation=1), ST7789 driver with built-in bitmap fonts.

Zone A (top ~105px): Time + timezone label
Zone B (bottom ~65px): Date, satellite info, fix status, coordinates, grid
"""

import st7789
import vga1_bold_16x32 as font_big
import vga1_bold_16x16 as font_small

# Colors (RGB565)
WHITE = st7789.color565(255, 255, 255)
BLACK = st7789.color565(0, 0, 0)
GREEN = st7789.color565(0, 255, 0)
RED = st7789.color565(255, 0, 0)
CYAN = st7789.color565(0, 255, 255)
YELLOW = st7789.color565(255, 255, 0)
ORANGE = st7789.color565(255, 165, 0)
GRAY = st7789.color565(128, 128, 128)
DARK_GRAY = st7789.color565(40, 40, 40)

# Layout constants
SCREEN_W = 320
SCREEN_H = 170
ZONE_A_H = 105
ZONE_B_Y = ZONE_A_H

# Zone A: time centered
TIME_Y = 20
TZ_LABEL_Y = 72

# Zone B: two rows of info, 16px font
ROW1_Y = ZONE_B_Y + 8
ROW2_Y = ZONE_B_Y + 32

# Separator line
SEP_Y = ZONE_A_H - 2


class DisplayManager:
    def __init__(self, tft):
        self._tft = tft
        self._cache = {}
        self._first_draw = True

    def init_screen(self):
        """Clear screen and draw static elements."""
        self._tft.fill(BLACK)
        # Draw separator line
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
        self._tft.text(font, text, x, y, color, BLACK)

    def update(self, gps, tz):
        """Refresh all display regions with current GPS and timezone data."""
        self._update_time(gps, tz)
        self._update_tz_label(tz)
        self._update_gps_info(gps, tz)
        self._first_draw = False

    def _update_time(self, gps, tz):
        """Draw time in large font, centered in Zone A."""
        if gps.time_is_valid:
            time_text = gps.time_str(tz.offset)
            color = WHITE
        else:
            time_text = "--:--:--"
            color = GRAY

        # 8 chars * 16px = 128px wide; center in 320px
        x = (SCREEN_W - len(time_text) * 16) // 2
        self._draw_text_if_changed("time", time_text, x, TIME_Y, font_big, color, clear_width=128)

    def _update_tz_label(self, tz):
        """Draw timezone label centered below time."""
        label = tz.label
        x = (SCREEN_W - len(label) * 16) // 2
        self._draw_text_if_changed("tz", label, x, TZ_LABEL_Y, font_small, CYAN, clear_width=SCREEN_W)

    def _update_gps_info(self, gps, tz):
        """Draw GPS info in Zone B: date, satellites, fix, coords, grid."""
        if not gps.has_ever_had_fix:
            # No fix ever — show acquiring message
            self._draw_text_if_changed(
                "status", "Acquiring satellites...",
                16, ROW1_Y + 12, font_small, ORANGE, clear_width=SCREEN_W - 32,
            )
            # Clear row areas that might have old data
            self._draw_text_if_changed("date", "", 0, ROW1_Y, font_small, BLACK, clear_width=0)
            self._draw_text_if_changed("sats", "", 0, 0, font_small, BLACK, clear_width=0)
            self._draw_text_if_changed("fix", "", 0, 0, font_small, BLACK, clear_width=0)
            self._draw_text_if_changed("lat", "", 0, 0, font_small, BLACK, clear_width=0)
            self._draw_text_if_changed("lon", "", 0, 0, font_small, BLACK, clear_width=0)
            self._draw_text_if_changed("grid", "", 0, 0, font_small, BLACK, clear_width=0)
            return

        # Clear acquiring message area if we now have data
        self._draw_text_if_changed("status", "", 0, 0, font_small, BLACK, clear_width=0)

        # Row 1: Date | Sat:U/V | Fix:type
        date_text = gps.date_str(tz.offset)
        self._draw_text_if_changed("date", date_text, 4, ROW1_Y, font_small, YELLOW, clear_width=176)

        sat_text = "Sat:{}/{}".format(gps.satellites_in_use, gps.satellites_in_view)
        self._draw_text_if_changed("sats", sat_text, 184, ROW1_Y, font_small, WHITE, clear_width=96)

        fix_text = "Fix:{}".format(gps.fix_type_str)
        fix_color = GREEN if gps.has_fix else RED
        self._draw_text_if_changed("fix", fix_text, 272, ROW1_Y, font_small, fix_color, clear_width=48)

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

        self._draw_text_if_changed("lat", lat_text, 4, ROW2_Y, font_small, coord_color, clear_width=144)
        self._draw_text_if_changed("lon", lon_text, 148, ROW2_Y, font_small, coord_color, clear_width=112)
        self._draw_text_if_changed("grid", grid_text, 260, ROW2_Y, font_small, CYAN, clear_width=60)

        # Signal lost warning (had fix before, lost it now)
        if not gps.has_fix:
            self._draw_text_if_changed(
                "warn", "Signal lost", 200, ZONE_B_Y + 52, font_small, RED, clear_width=120,
            )
        else:
            self._draw_text_if_changed("warn", "", 200, ZONE_B_Y + 52, font_small, BLACK, clear_width=120)
