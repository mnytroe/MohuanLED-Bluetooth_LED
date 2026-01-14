"""Custom exceptions for the bluelights library."""

from __future__ import annotations


class BlueLightsError(Exception):
    """Base exception for all bluelights errors."""

    pass


class LEDConnectionError(BlueLightsError):
    """Raised when connection to the LED device fails."""

    def __init__(self, message: str = "Failed to connect to LED device", mac_address: str | None = None) -> None:
        self.mac_address = mac_address
        if mac_address:
            message = f"{message} (MAC: {mac_address})"
        super().__init__(message)


class LEDNotFoundError(BlueLightsError):
    """Raised when no LED device is found during scanning."""

    def __init__(self, message: str = "No LED device found. Ensure the device is powered on and within range.") -> None:
        super().__init__(message)


class LEDCommandError(BlueLightsError):
    """Raised when sending a command to the LED device fails."""

    def __init__(self, message: str = "Failed to send command to LED device", command: bytes | None = None) -> None:
        self.command = command
        if command:
            message = f"{message} (command: {command.hex()})"
        super().__init__(message)


class LEDUUIDError(BlueLightsError):
    """Raised when no compatible UUID is found for the LED device."""

    def __init__(self, message: str = "No compatible UUID found for the LED device") -> None:
        super().__init__(message)


class LEDValueError(BlueLightsError):
    """Raised when an invalid value is provided to an LED method."""

    pass
