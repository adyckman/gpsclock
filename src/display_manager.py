"""Display layout and partial-update rendering for the GPS clock.

320x170 landscape (rotation=1), ST7789 driver with fixed_v01 font.

Zone A (top): Local time + TZ + date, UTC time + date below
Zone B (bottom): Satellite info, fix status, coordinates, grid square
"""

import st7789
import fixed_v01_16 as font_big
import fixed_v01_8 as font_small

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

# Character metrics
CHAR_W_BIG = 12    # fixed_v01_16: 12px wide, 18px tall
CHAR_W_SMALL = 6   # fixed_v01_8: 6px wide, 9px tall

# Zone A: time lines (big font)
DATE_X = 20                                     # "YYYY-MM-DD" first
LINE1_Y = 24
LINE2_Y = 46                                   # 24 + 18 + 4
TIME_X = DATE_X + 10 * CHAR_W_BIG + 8          # "HH:MM:SS" after date
LABEL_X = TIME_X + 8 * CHAR_W_BIG + 8          # TZ / "UTC" after time

# Separator
SEP_Y = 68

# Zone B: GPS info rows (small font)
ROW1_Y = 78
ROW2_Y = 94
ROW3_Y = 110
ROW4_Y = 126

# Status message area
STATUS_X = 8
STATUS_Y = 142
STATUS_CLEAR_W = 180


class DisplayManager:
    def __init__(self, tft):
        self._tft = tft
        self._cache = {}
        self._first_draw = True
        # Raw value caches to skip formatting when unchanged
        self._last_siu = -1
        self._last_siv = -1
        self._last_fix_type = -1
        self._last_has_fix = None
        self._last_temp = None
        self._last_hum = None

    def init_screen(self):
        """Clear screen and draw static elements."""
        self._tft.fill(BLACK)
        self._tft.hline(0, SEP_Y, SCREEN_W, GRAY)
        self._first_draw = True
        self._cache.clear()

    def _draw_text(self, key, text, x, y, font, color, clear_width=0):
        """Only redraw text if it has changed since last call with this key."""
        prev = self._cache.get(key)
        if prev is not None and prev[0] == text and prev[1] == color and not self._first_draw:
            return
        self._cache[key] = (text, color)
        if clear_width > 0:
            self._tft.fill_rect(x, y, clear_width, font.HEIGHT, BLACK)
        if text:
            self._tft.write(font, text, x, y, color, BLACK)

    def update(self, gps, tz, dht=None):
        """Refresh all display regions with current GPS and timezone data."""
        if gps.time_is_valid:
            tz.update_dst(gps.utc_year, gps.utc_month, gps.utc_day, gps.hours)
        self._update_time(gps, tz)
        self._update_gps_info(gps, tz)
        if dht is not None:
            self._update_dht(dht)
        self._first_draw = False

    def _update_time(self, gps, tz):
        """Draw local time + TZ + date, and UTC time + date."""
        if gps.time_is_valid:
            local_time = gps.time_str(tz.offset)
            utc_time = gps.time_str(0)
            time_color = WHITE
            utc_color = GRAY
            date_color = YELLOW
            utc_date_color = GRAY
        else:
            local_time = "--:--:--"
            utc_time = "--:--:--"
            time_color = GRAY
            utc_color = GRAY
            date_color = GRAY
            utc_date_color = GRAY

        local_date = gps.date_str(tz.offset)
        utc_date = gps.date_str(0)

        # Line 1: date + local time + TZ
        self._draw_text("local_date", local_date, DATE_X, LINE1_Y,
                         font_big, date_color, clear_width=126)
        self._draw_text("time", local_time, TIME_X, LINE1_Y,
                         font_big, time_color, clear_width=102)
        self._draw_text("tz", tz.abbreviation, LABEL_X, LINE1_Y,
                         font_big, CYAN, clear_width=54)

        # Line 2: date + UTC time + "UTC"
        self._draw_text("utc_date", utc_date, DATE_X, LINE2_Y,
                         font_big, utc_date_color, clear_width=126)
        self._draw_text("utc_time", utc_time, TIME_X, LINE2_Y,
                         font_big, utc_color, clear_width=102)
        self._draw_text("utc_label", "UTC", LABEL_X, LINE2_Y,
                         font_big, CYAN, clear_width=54)

    def _update_gps_info(self, gps, tz):
        """Draw GPS info in Zone B: satellites, fix, coords, grid."""
        if not gps.has_ever_had_fix:
            self._draw_text("status", "Acquiring satellites...",
                             STATUS_X, STATUS_Y, font_small, ORANGE,
                             clear_width=STATUS_CLEAR_W)
            for key in ("sats", "fix", "lat", "lon", "grid", "utm"):
                self._cache[key] = ("", BLACK)
            return

        # Clear acquiring message when we first get a fix
        self._draw_text("status", "", STATUS_X, STATUS_Y,
                         font_small, BLACK, clear_width=STATUS_CLEAR_W)

        # Row 1: Sat:U/V | Fix:type
        siu = gps.satellites_in_use
        siv = gps.satellites_in_view
        if siu != self._last_siu or siv != self._last_siv or self._first_draw:
            self._last_siu = siu
            self._last_siv = siv
            self._draw_text("sats", "Sat:{}/{}".format(siu, siv), 8, ROW1_Y,
                             font_small, WHITE, clear_width=60)

        ft = gps.fix_type_str
        hf = gps.has_fix
        if ft != self._last_fix_type or hf != self._last_has_fix or self._first_draw:
            self._last_fix_type = ft
            self._last_has_fix = hf
            self._draw_text("fix", "Fix:{}".format(ft), 96, ROW1_Y,
                             font_small, GREEN if hf else RED, clear_width=48)

        # Row 2: Lat | Lon | Grid
        if gps.has_fix:
            lat_text = gps.lat_str()
            lon_text = gps.lon_str()
            grid_text = gps.maidenhead
            utm_text = gps.utm
            coord_color = WHITE
        else:
            lat_text = "-- N"
            lon_text = "-- W"
            grid_text = "------"
            utm_text = "-- --E --N"
            coord_color = GRAY

        self._draw_text("lat", lat_text, 8, ROW2_Y,
                         font_small, coord_color, clear_width=72)
        self._draw_text("lon", lon_text, 84, ROW2_Y,
                         font_small, coord_color, clear_width=78)
        self._draw_text("grid", grid_text, 168, ROW2_Y,
                         font_small, CYAN, clear_width=42)

        # Row 3: UTM
        self._draw_text("utm", utm_text, 8, ROW3_Y,
                         font_small, coord_color, clear_width=130)

        # Signal lost warning
        if not gps.has_fix:
            self._draw_text("status", "Signal lost",
                             STATUS_X, STATUS_Y, font_small, RED,
                             clear_width=STATUS_CLEAR_W)

    def _update_dht(self, dht):
        """Draw temperature and humidity on ROW4."""
        if dht.has_reading:
            t = dht.temperature_f
            h = dht.humidity
            if t != self._last_temp or h != self._last_hum or self._first_draw:
                self._last_temp = t
                self._last_hum = h
                self._draw_text("temp", "{:.1f}F".format(t), 8, ROW4_Y,
                                 font_small, WHITE, clear_width=42)
                self._draw_text("hum", "{:.1f}%".format(h), 60, ROW4_Y,
                                 font_small, WHITE, clear_width=36)
        elif self._last_temp is not None or self._first_draw:
            self._last_temp = None
            self._last_hum = None
            self._draw_text("temp", "--.-F", 8, ROW4_Y,
                             font_small, GRAY, clear_width=42)
            self._draw_text("hum", "--.-%", 60, ROW4_Y,
                             font_small, GRAY, clear_width=36)
