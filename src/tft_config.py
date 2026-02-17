"""LilyGo T-DISPLAY-S3 170x320 ST7789 display configuration.

Reference: russhughes/st7789s3_mpy
Parallel 8-bit interface with pins:
  D0-D7: GPIO 39-42, 45-48
  WR: 8, RD: 9, CS: 6, DC: 7, RST: 5, BL: 38
  LCD Power: GPIO15
"""

from machine import Pin, freq
import st7789

freq(240000000)

TFA = 0
BFA = 0


def config(rotation=0, buffer_size=0, options=0):
    LCD_POWER = Pin(15, Pin.OUT)
    LCD_POWER.value(1)

    return st7789.ST7789(
        Pin(48, Pin.OUT),
        Pin(47, Pin.OUT),
        Pin(46, Pin.OUT),
        Pin(45, Pin.OUT),
        Pin(42, Pin.OUT),
        Pin(41, Pin.OUT),
        Pin(40, Pin.OUT),
        Pin(39, Pin.OUT),
        Pin(8, Pin.OUT),
        Pin(9, Pin.OUT),
        170,
        320,
        reset=Pin(5, Pin.OUT),
        cs=Pin(6, Pin.OUT),
        dc=Pin(7, Pin.OUT),
        rotation=rotation,
        options=options,
        buffer_size=buffer_size,
    )
