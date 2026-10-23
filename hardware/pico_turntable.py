"""MicroPython firmware for an A4988-driven, low-speed item turntable.

Wire GP2 to DIR, GP3 to STEP, GP4 to ENABLE. Set the A4988 microstep pins
MS1 and MS2 high and MS3 low for 1/8 microstepping. Motor power must come
from a separate, current-limited supply. Keep the physical stop switch in
series with the driver's ENABLE/power path; software is not an emergency stop.
"""

import sys
import time
from machine import Pin


direction = Pin(2, Pin.OUT, value=0)
step = Pin(3, Pin.OUT, value=0)
enable = Pin(4, Pin.OUT, value=1)  # A4988 ENABLE is active low.
ms1 = Pin(5, Pin.OUT, value=1)
ms2 = Pin(6, Pin.OUT, value=1)
ms3 = Pin(7, Pin.OUT, value=0)

enable.value(0)
step_counts = (533, 534, 533)  # Adds to exactly 1,600 microsteps per rotation.
view_index = 0
delay_us = 1800


def rotate_to_next_view():
    global view_index
    count = step_counts[view_index]
    for _ in range(count):
        step.value(1)
        time.sleep_us(delay_us)
        step.value(0)
        time.sleep_us(delay_us)
    view_index = (view_index + 1) % len(step_counts)
    return view_index


while True:
    command = sys.stdin.readline().strip().upper()
    if command == "ROTATE":
        position = rotate_to_next_view()
        print("OK VIEW=" + str(position + 1))
    elif command == "DISABLE":
        enable.value(1)
        print("OK DISABLED")
    elif command == "ENABLE":
        enable.value(0)
        print("OK ENABLED")
    elif command:
        print("ERR UNKNOWN COMMAND")
