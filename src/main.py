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

    # --- Init display manager ---
    from display_manager import DisplayManager
    dm = DisplayManager(tft)
    dm.init_screen()

    # --- Main loop ---
    last_display = time.ticks_ms()

    while True:
        # Drain UART buffer every iteration
        gps.feed()

        # Check buttons every iteration for responsive feel
        bl.check_button()
        if tz.check_button():
            # Force immediate display refresh on timezone change
            dm.update(gps, tz)
            last_display = time.ticks_ms()

        # Throttled display update
        now = time.ticks_ms()
        if time.ticks_diff(now, last_display) >= _DISPLAY_INTERVAL_MS:
            dm.update(gps, tz)
            last_display = now

        time.sleep_ms(10)


try:
    main()
except Exception as e:
    sys.print_exception(e)
    # Keep running so display stays powered for debugging
    while True:
        time.sleep_ms(1000)
