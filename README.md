# GPS Clock

MicroPython firmware for the **LILYGO T-Display-S3** (ESP32-S3, ST7789 170x320 LCD) that displays real-time GPS clock data from a **BN-220 GPS module**.

## Features

- 24-hour GPS-synchronized clock displayed in large 32px font
- Date, satellite count, fix status, coordinates, and Maidenhead grid locator
- Button cycles through 6 US timezones (Eastern, Central, Mountain, Pacific, Alaska, Hawaii)
- Partial-update rendering — only redraws changed regions to minimize flicker
- Color-coded display: green/red fix status, yellow date, cyan timezone, orange warnings
- Persistent time display after momentary GPS signal loss
- Timezone-aware date handling (correct midnight crossing)

## Display Layout

```
+------------------------------------------------------------------+
|  ZONE A: Time (top ~105px)                                       |
|                                                                  |
|              14:34:56          (white, 16x32 font)               |
|                                                                  |
|           US Eastern (UTC-5)   (cyan, 16x16 font)               |
+==================================================================+
|  ZONE B: GPS Info (bottom ~65px, 16x16 font)                    |
|                                                                  |
|  2026-02-10          Sat:8/12        Fix:3D                     |
|  40.7128 N           74.0060 W       FN20ir                     |
+------------------------------------------------------------------+
```

## Hardware

### Requirements

- [LILYGO T-Display-S3](http://www.lilygo.cc/products/t-display-s3) (ESP32-S3 with ST7789 170x320 LCD)
- [BN-220 GPS module](https://www.u-blox.com/) (9600 baud, NMEA output)
- Custom MicroPython firmware from [russhughes/st7789s3_mpy](https://github.com/russhughes/st7789s3_mpy) (includes the `st7789` C driver and built-in bitmap fonts)

> **Note:** Standard MicroPython does not include the ST7789 parallel driver. You must flash the custom firmware first.

### Wiring

| BN-220 | T-Display-S3 | Note                  |
|--------|--------------|-----------------------|
| TX     | GPIO2 (RX)   | GPS sends to ESP32    |
| RX     | GPIO1 (TX)   | Unused but connected  |
| VCC    | 3.3V         | BN-220 accepts 2.7-5V |
| GND    | GND          | Common ground         |

The timezone button uses the onboard button connected to **GPIO14**.

## File Structure

```
src/
  main.py              # Entry point, main loop
  tft_config.py        # Display hardware init (parallel 8-bit pins)
  gps_reader.py        # UART GPS + micropyGPS wrapper
  display_manager.py   # Screen layout and partial-update rendering
  timezone.py          # US timezone definitions + button handler
  micropyGPS.py        # Vendored from inmcm/micropyGPS
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
Display hardware configuration from the st7789s3_mpy reference. Sets CPU to 240MHz, enables LCD power (GPIO15), configures 8-bit parallel data pins and control pins.

### `micropyGPS.py`
Vendored single-file NMEA parser from [inmcm/micropyGPS](https://github.com/inmcm/micropyGPS). Parses GPRMC, GPGGA, GPGSA, GPGSV, GPGLL, and GPVTG sentences with GP/GL/GN prefix support.

### `timezone.py`
Defines 6 US timezones with standard time UTC offsets. GPIO14 button with pull-up and 250ms debounce cycles through zones on each press.

### `gps_reader.py`
Wraps UART1 (9600 baud) and the MicropyGPS parser. Provides:
- Time/date strings adjusted for timezone offset (handles UTC midnight crossing)
- Decimal degree coordinates converted from DMS tuples
- 6-character Maidenhead grid locator
- Fix tracking (`has_ever_had_fix` for persistent display after signal loss)

### `display_manager.py`
Two-zone screen layout with cached partial updates. Each text region is tracked by key — only redrawn when the value changes. Uses `vga1_bold_16x32` for time and `vga1_bold_16x16` for GPS info.

### `main.py`
Initialization sequence (display, GPS, timezone, display manager) followed by the main loop:
- GPS `feed()` every 10ms iteration (drains UART buffer)
- Button `check_button()` every iteration (responsive feel)
- Display `update()` throttled to every 200ms
- Top-level exception handler keeps display powered for debugging

## Verification

1. **Display test:** `import tft_config; tft = tft_config.config(rotation=1); tft.init(); tft.fill(0x07E0)` — screen turns green
2. **GPS test:** Create `GPSReader`, call `feed()` in a loop, print `gps.has_fix` and `gps.date_str()`
3. **Button test:** Create `TimezoneManager`, poll `check_button()`, verify timezone cycles
4. **Full integration:** Upload all files, power cycle, verify clock after GPS fix

## Known Limitations

- **No DST handling** — offsets are standard time only
- **Timezone resets on reboot** — defaults to Eastern, not persisted
- **Font size** — uses 32px built-in font; larger custom fonts require running `font2bitmap.py` on the host and uploading the result
