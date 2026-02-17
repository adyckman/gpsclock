# GPS Clock

MicroPython firmware for the **LILYGO T-Display-S3** (ESP32-S3, ST7789 170x320 LCD) that displays real-time GPS clock data from a **BN-220 GPS module**.

## Features

- 24-hour GPS-synchronized clock with local time and UTC time
- Date, satellite count, fix status, coordinates, Maidenhead grid locator, and UTM
- Raw NMEA passthrough to USB — connected devices can use the clock as a GPS source
- Button cycles through 6 US timezones (Eastern, Central, Mountain, Pacific, Alaska, Hawaii)
- Partial-update rendering — only redraws changed regions to minimize flicker
- Color-coded display: green/red fix status, yellow date, cyan timezone, orange warnings
- Persistent time display after momentary GPS signal loss
- Timezone-aware date handling (correct midnight crossing)

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
+------------------------------------------------------------------+
```

Zone A uses the **fixed_v01** font at size 16 (12x18px). Zone B uses size 8 (6x9px).

## Hardware

### Requirements

- [LILYGO T-Display-S3](http://www.lilygo.cc/products/t-display-s3) (ESP32-S3 with ST7789 170x320 LCD)
- [BN-220 GPS module](https://www.u-blox.com/) (9600 baud, NMEA output)
- Custom MicroPython firmware from [russhughes/st7789s3_mpy](https://github.com/russhughes/st7789s3_mpy) (includes the `st7789` C driver)

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
  gps_reader.py        # UART GPS + micropyGPS wrapper, NMEA USB passthrough
  display_manager.py   # Screen layout and partial-update rendering
  timezone.py          # US timezone definitions + button handler
  micropyGPS.py        # Vendored from inmcm/micropyGPS
  fixed_v01_8.py       # Bitmap font module (fixed_v01 at size 8, Zone B)
  fixed_v01_16.py      # Bitmap font module (fixed_v01 at size 16, Zone A)
utils/
  font2bitmap.py       # TTF-to-bitmap font converter (host-side tool)
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
- Decimal degree coordinates (6 decimal places) converted from DMS tuples
- 6-character Maidenhead grid locator
- UTM coordinates (WGS84 Transverse Mercator)
- Fix tracking (`has_ever_had_fix` for persistent display after signal loss)
- Raw NMEA passthrough to USB (`sys.stdout.buffer`) for external device consumption

### `display_manager.py`
Two-zone screen layout with cached partial updates. Each text region is tracked by key — only redrawn when the value changes. Zone A (date + time) uses `fixed_v01` at size 16, Zone B (GPS info) uses size 8.

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

## Using with gpsd

The clock outputs raw NMEA sentences on USB. To use it with `gpsd`, a read-only proxy is needed to prevent gpsd's probe commands from disrupting the firmware:

```bash
sudo systemctl stop gpsd.socket gpsd
sudo socat -u /dev/ttyACM0,raw,echo=0,b9600 PTY,link=/dev/gps,raw,mode=666 &
sudo gpsd /dev/gps -n
cgps
```

This creates a one-way PTY via `socat` so gpsd can read NMEA data without writing to the ESP32. The device path may vary (`ttyACM0`, `ttyACM1`) — check `ls /dev/ttyACM*`.

## Known Limitations

- **No DST handling** — offsets are standard time only
- **Timezone resets on reboot** — defaults to Eastern, not persisted
- **gpsd requires socat proxy** — direct connection freezes the firmware due to gpsd's protocol probing
