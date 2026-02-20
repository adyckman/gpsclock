# GPS Clock

MicroPython firmware for the **LILYGO T-Display-S3** (ESP32-S3, ST7789 170x320 LCD) that displays real-time GPS clock data from a **BN-220 GPS module**.

## Features

- 24-hour GPS-synchronized clock with local time and UTC time
- Date, satellite count, fix status, coordinates, Maidenhead grid locator, and UTM
- Raw NMEA passthrough to USB — connected devices can use the clock as a GPS source
- Adjustable backlight brightness via boot button (GPIO0, 5 levels)
- Automatic US daylight saving time (spring forward / fall back)
- Automatic timezone detection from GPS coordinates on first fix (0.25° grid, ~17 mile resolution)
- Button short press cycles through 7 US timezones; long press (1s) re-detects from GPS location
- Partial-update rendering — only redraws changed regions to minimize flicker
- Color-coded display: green/red fix status, yellow date, cyan timezone, orange warnings
- Persistent time display after momentary GPS signal loss
- Timezone-aware date handling (correct midnight crossing)
- DHT22 temperature (°F) and humidity display

## Display Layout

```
+------------------------------------------------------------------+
|  ZONE A: Date + Time (12x18 font)                                |
|                                                                  |
|  2026-02-10  14:34:56  EST     (yellow / white / cyan)           |
|  2026-02-10  19:34:56  UTC     (gray / gray / cyan)              |
+==================================================================+
|  ZONE B: GPS Info (6x9 font)                                    |
|                                                                  |
|  Sat:8/12  Fix:3D                                                |
|  40.712800 N  74.006000 W  FN20ir                                |
|  18T 583960E 4507523N                                            |
|  72.4F  45.2%                                                    |
+------------------------------------------------------------------+
```

Zone A uses the **fixed_v01** font at size 16 (12x18px). Zone B uses size 8 (6x9px).

## Hardware

### Requirements

- [LILYGO T-Display-S3](http://www.lilygo.cc/products/t-display-s3) (ESP32-S3 with ST7789 170x320 LCD)
- [BN-220 GPS module](https://www.u-blox.com/) (9600 baud, NMEA output)
- DHT22 temperature/humidity sensor on GPIO16
- Custom MicroPython firmware from [russhughes/st7789s3_mpy](https://github.com/russhughes/st7789s3_mpy) (includes the `st7789` C driver)

> **Note:** Standard MicroPython does not include the ST7789 parallel driver. You must flash the custom firmware first.

### Wiring

| BN-220 | T-Display-S3 | Note                  |
|--------|--------------|-----------------------|
| TX     | GPIO2 (RX)   | GPS sends to ESP32    |
| RX     | GPIO1 (TX)   | Unused but connected  |
| VCC    | 3.3V         | BN-220 accepts 2.7-5V |
| GND    | GND          | Common ground         |

| DHT22    | T-Display-S3 | Note                  |
|----------|--------------|-----------------------|
| DATA     | GPIO16       | 10k pull-up to 3.3V   |
| VCC      | 3.3V         | DHT22 accepts 3.3-5V  |
| GND      | GND          | Common ground         |

The timezone button uses the onboard button connected to **GPIO14**. The boot button on **GPIO0** controls backlight brightness.

## File Structure

```
src/
  main.py              # Entry point, main loop
  tft_config.py        # Display hardware init (parallel 8-bit pins)
  gps_reader.py        # UART GPS + micropyGPS wrapper, NMEA USB passthrough
  display_manager.py   # Screen layout and partial-update rendering
  dht_reader.py        # DHT22 temperature/humidity sensor reader
  brightness.py        # Backlight PWM control + boot button handler
  timezone.py          # US timezone definitions + button handler
  tz_grid.py           # Precomputed timezone boundary grid (auto-generated)
  micropyGPS.py        # Stripped-down NMEA parser (from inmcm/micropyGPS)
  fixed_v01_8.py       # Bitmap font module (fixed_v01 at size 8, Zone B)
  fixed_v01_16.py      # Bitmap font module (fixed_v01 at size 16, Zone A)
utils/
  font2bitmap.py       # TTF-to-bitmap font converter (host-side tool)
  gen_tz_grid.py       # Timezone grid generator (host-side tool)
```

## Installation

1. Flash the [st7789s3_mpy](https://github.com/russhughes/st7789s3_mpy) firmware to the T-Display-S3.

2. Upload all source files to the device root:

   ```bash
   mpremote cp src/*.py :
   ```

3. Reset the board. The clock will start and display "Acquiring satellites..." until a GPS fix is obtained (may take 30-60 seconds outdoors).

## Module Overview

### `tft_config.py`
Display hardware configuration from the st7789s3_mpy reference. Sets CPU to 240MHz, enables LCD power (GPIO15), configures 8-bit parallel data pins and control pins. Backlight pin (GPIO38) is managed separately by `brightness.py` via PWM.

### `micropyGPS.py`
Stripped-down NMEA parser based on [inmcm/micropyGPS](https://github.com/inmcm/micropyGPS). Parses GPRMC, GPGGA, GPGSA, and GPGSV sentences with GP/GL/GN prefix support. Optimized for low RAM: accepts raw bytes (no chr/ord overhead), uses a bytearray buffer with single decode+split per sentence instead of per-character string concatenation, and removes unused features (VTG/GLL parsers, logging, speed/course/altitude tracking, satellite detail dict, helper methods).

### `timezone.py`
Defines 7 US timezones with automatic DST support. Computes DST transitions (2nd Sunday of March, 1st Sunday of November) from the GPS date and adjusts offset and abbreviation accordingly. DST result is cached and only recomputed when the UTC hour or day changes. Arizona and Hawaii are marked as non-DST. GPIO14 button with 250ms debounce: short press cycles through zones, long press (>=1s) re-detects timezone from current GPS coordinates. On first GPS fix, auto-detects the timezone from coordinates using `tz_grid.py`; manual button presses take priority over auto-detection.

### `tz_grid.py`
Precomputed US timezone boundary grid at 0.25° resolution (~17 miles), auto-generated by `utils/gen_tz_grid.py`. Stores 3 longitude boundaries per latitude row (Pacific/Mountain, Mountain/Central, Central/Eastern) in a 312-byte array. Handles Alaska and Hawaii via simple bounds checks, and Arizona via a rectangle check within the Mountain zone. The `lookup(lat, lon)` function returns a timezone index in O(1).

### `gps_reader.py`
Wraps UART1 (9600 baud) and the MicropyGPS parser. Provides:
- Time/date strings adjusted for timezone offset (handles UTC midnight crossing)
- Decimal degree coordinates (6 decimal places) converted from DMS tuples, cached until position changes
- 6-character Maidenhead grid locator (cached, recomputed only on position change)
- UTM coordinates (WGS84 Transverse Mercator, cached, recomputed only on position change)
- Fix tracking (`has_ever_had_fix` for persistent display after signal loss)
- Raw NMEA passthrough to USB (`sys.stdout.buffer`) for external device consumption

### `display_manager.py`
Two-zone screen layout with cached partial updates. Each text region is tracked by key — only redrawn when the value changes. Zone A (date + time) uses `fixed_v01` at size 16, Zone B (GPS info) uses size 8.

### `dht_reader.py`
Reads a DHT22 sensor on GPIO16 with a 2-second polling interval (the hardware minimum). Keeps the last good reading on sensor errors. Exposes temperature in Fahrenheit and relative humidity percentage.

### `brightness.py`
PWM backlight control on GPIO38 (1kHz). Boot button (GPIO0) with pull-up and 250ms debounce cycles through 5 brightness levels (100%, 75%, 50%, 25%, 6%).

### `main.py`
Initialization sequence (display, GPS, timezone, brightness, DHT22, display manager) followed by the main loop:
- GPS `feed()` every 10ms iteration (drains UART buffer)
- Auto-detect timezone on first GPS fix (one-time)
- Brightness and timezone buttons checked every iteration (responsive feel)
- Display `update()` throttled to every 200ms
- Top-level exception handler keeps display powered for debugging

## Verification

1. **Display test:** `import tft_config; tft = tft_config.config(rotation=1); tft.init(); tft.fill(0x07E0)` — screen turns green
2. **GPS test:** Create `GPSReader`, call `feed()` in a loop, print `gps.has_fix` and `gps.date_str()`
3. **Button test:** Create `TimezoneManager`, poll `check_button()`, verify timezone cycles
4. **Full integration:** Upload all files, power cycle, verify clock after GPS fix

## Using with gpsd

The clock outputs raw NMEA sentences on USB. To use it with `gpsd`, the `-b` (read-only) flag is required to prevent gpsd's protocol probe commands from disrupting the firmware:

```bash
sudo systemctl stop gpsd.socket gpsd
sudo gpsd -b -n /dev/ttyACM0
cgps
```

The device path may vary (`ttyACM0`, `ttyACM1`) — check `ls /dev/ttyACM*`.

## Known Limitations

- **Timezone resets on reboot** — auto-detected from GPS on next fix, but not persisted across power cycles
- **Timezone grid is approximate** — boundaries follow simplified state/region lines at 0.25° resolution; use the button to correct if needed
- **gpsd requires `-b` flag** — without it, gpsd's protocol probing freezes the firmware
