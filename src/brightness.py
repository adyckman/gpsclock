"""Backlight brightness control via PWM on GPIO38, cycled by boot button (GPIO0)."""

from machine import Pin, PWM
import time

_LEVELS = (65535, 49151, 32768, 16384, 4096)
_DEBOUNCE_MS = 250


class BrightnessController:
    def __init__(self, backlight_pin=38, button_pin=0):
        self._pwm = PWM(Pin(backlight_pin), freq=1000, duty_u16=_LEVELS[0])
        self._button = Pin(button_pin, Pin.IN, Pin.PULL_UP)
        self._index = 0
        self._last_press = 0

    def check_button(self):
        """Poll boot button; cycles brightness on press."""
        if self._button.value() == 0:
            now = time.ticks_ms()
            if time.ticks_diff(now, self._last_press) > _DEBOUNCE_MS:
                self._last_press = now
                self._index = (self._index + 1) % len(_LEVELS)
                self._pwm.duty_u16(_LEVELS[self._index])
