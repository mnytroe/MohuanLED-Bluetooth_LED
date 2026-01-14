"""
BlueLights - Bluetooth LED control library for MohuanLED devices.

This library provides an async Python API for controlling MohuanLED brand
Bluetooth LED devices. It supports device discovery, color control, and
various lighting effects.

Example:
    from bluelights import BJLEDInstance

    async def main():
        async with BJLEDInstance() as led:
            await led.turn_on()
            await led.set_color_to_rgb(255, 0, 0)  # Red
            await led.rainbow_cycle(5.0)
            await led.turn_off()

    asyncio.run(main())
"""

from __future__ import annotations

from .commands import (
    BREATHING_STEPS,
    DEFAULT_CONNECTION_RETRIES,
    DEFAULT_CONNECTION_TIMEOUT,
    DEFAULT_EFFECT_SPEED,
    DEFAULT_RETRY_DELAY,
    DEFAULT_SCAN_TIMEOUT,
    DEFAULT_WRITE_TIMEOUT,
    FADE_STEPS,
    LEDCommand,
    LEDDeviceInfo,
    RAINBOW_HUE_STEPS,
    build_color_command,
)
from .exceptions import (
    BlueLightsError,
    LEDCommandError,
    LEDConnectionError,
    LEDNotFoundError,
    LEDOperationCancelledError,
    LEDTimeoutError,
    LEDUUIDError,
    LEDValueError,
)
from .manager import BJLEDInstance
from .scanner import Scanner

__all__ = [
    # Main classes
    "BJLEDInstance",
    "Scanner",
    # Exceptions
    "BlueLightsError",
    "LEDCommandError",
    "LEDConnectionError",
    "LEDNotFoundError",
    "LEDOperationCancelledError",
    "LEDTimeoutError",
    "LEDUUIDError",
    "LEDValueError",
    # Commands and utilities
    "LEDCommand",
    "LEDDeviceInfo",
    "build_color_command",
    # Constants
    "BREATHING_STEPS",
    "DEFAULT_CONNECTION_RETRIES",
    "DEFAULT_CONNECTION_TIMEOUT",
    "DEFAULT_EFFECT_SPEED",
    "DEFAULT_RETRY_DELAY",
    "DEFAULT_SCAN_TIMEOUT",
    "DEFAULT_WRITE_TIMEOUT",
    "FADE_STEPS",
    "RAINBOW_HUE_STEPS",
]

__version__ = "1.0.0"
