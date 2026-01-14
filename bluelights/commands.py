"""BLE command constants for MohuanLED devices."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LEDCommand(Enum):
    """Enumeration of LED command prefixes."""

    TURN_ON = bytearray.fromhex("69 96 02 01 01")
    TURN_OFF = bytearray.fromhex("69 96 02 01 00")
    SET_COLOR_PREFIX = bytearray.fromhex("69 96 05 02")


@dataclass(frozen=True)
class LEDDeviceInfo:
    """Information about an LED device."""

    DEVICE_NAME_PREFIX: str = "BJ_LED_M"
    DEFAULT_BRIGHTNESS: int = 255
    MIN_RGB_VALUE: int = 0
    MAX_RGB_VALUE: int = 255
    MIN_BRIGHTNESS: int = 0
    MAX_BRIGHTNESS: int = 255


def build_color_command(red: int, green: int, blue: int) -> bytearray:
    """
    Build a color command packet for the LED device.

    Args:
        red: Red color value (0-255)
        green: Green color value (0-255)
        blue: Blue color value (0-255)

    Returns:
        bytearray: The complete command packet to send to the device
    """
    packet = bytearray(LEDCommand.SET_COLOR_PREFIX.value)
    packet.append(red)
    packet.append(green)
    packet.append(blue)
    return packet


def validate_rgb_value(value: int, name: str = "RGB") -> int:
    """
    Validate that an RGB value is within the valid range (0-255).

    Args:
        value: The value to validate
        name: The name of the parameter (for error messages)

    Returns:
        int: The validated value

    Raises:
        ValueError: If the value is outside the valid range
    """
    if not isinstance(value, int):
        raise TypeError(f"{name} value must be an integer, got {type(value).__name__}")
    if value < LEDDeviceInfo.MIN_RGB_VALUE or value > LEDDeviceInfo.MAX_RGB_VALUE:
        raise ValueError(f"{name} value must be between 0 and 255, got {value}")
    return value


def validate_brightness(value: int) -> int:
    """
    Validate that a brightness value is within the valid range (0-255).

    Args:
        value: The brightness value to validate

    Returns:
        int: The validated value

    Raises:
        ValueError: If the value is outside the valid range
    """
    return validate_rgb_value(value, "Brightness")
