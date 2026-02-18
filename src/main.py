"""GPS Clock main entry point for LILYGO T-Display-S3."""

import time
import sys

# Display update throttle (ms)
_DISPLAY_INTERVAL_MS = 200


def main():
    # --- Init display ---
    import tft_config
    tft = tft_config.config(rotation=1)
    tft.init()
    tft.fill(0)

    # --- Init GPS ---
    from gps_reader import GPSReader
    gps = GPSReader()

    # --- Init timezone ---
    from timezone import TimezoneManager
    tz = TimezoneManager()

    # --- Init brightness ---
    from brightness import BrightnessController
    bl = BrightnessController()

    # --- Init DHT22 sensor ---
    from dht_reader import DHTReader
    dht = DHTReader(pin=16)

    # --- Init display manager ---
    from display_manager import DisplayManager
    dm = DisplayManager(tft)
    dm.init_screen()

    # --- Main loop ---
    last_display = time.ticks_ms()
    auto_tz_done = False

    while True:
        # Drain UART buffer every iteration
        gps.feed()

        # Auto-detect timezone on first GPS fix
        if not auto_tz_done and gps.has_fix:
            if tz.set_from_location(gps.latitude_decimal, gps.longitude_decimal):
                dm.update(gps, tz, dht)
            auto_tz_done = True

        # Read DHT22 sensor (self-throttled to 2s intervals)
        dht.update()

        # Check buttons every iteration for responsive feel
        bl.check_button()
        tz_action = tz.check_button()
        if tz_action == 2 and gps.has_fix:
            # Long press — re-detect timezone from GPS location
            tz.set_from_location(gps.latitude_decimal, gps.longitude_decimal, force=True)
            dm.update(gps, tz, dht)
            last_display = time.ticks_ms()
        elif tz_action == 1:
            # Short press — cycle to next timezone
            dm.update(gps, tz, dht)
            last_display = time.ticks_ms()

        # Throttled display update
        now = time.ticks_ms()
        if time.ticks_diff(now, last_display) >= _DISPLAY_INTERVAL_MS:
            dm.update(gps, tz, dht)
            last_display = now

        time.sleep_ms(10)


try:
    main()
except Exception as e:
    sys.print_exception(e)
    # Keep running so display stays powered for debugging
    while True:
        time.sleep_ms(1000)
