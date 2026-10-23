"""Optional USB-serial control for the Raspberry Pi Pico turntable firmware."""

from __future__ import annotations

import os


def rotate_one_view() -> dict[str, object]:
    port = os.environ.get("FAR_TURNTABLE_PORT", "").strip()
    if not port:
        return {"rotated": False, "configured": False}
    try:
        import serial

        with serial.Serial(port, 115200, timeout=8, write_timeout=2) as device:
            device.reset_input_buffer()
            device.write(b"ROTATE\n")
            response = device.readline().decode("utf-8", errors="replace").strip()
        if not response.startswith("OK"):
            return {"rotated": False, "configured": True, "detail": response or "No reply from the tray controller."}
        return {"rotated": True, "configured": True}
    except Exception as error:
        return {"rotated": False, "configured": True, "detail": str(error)}
