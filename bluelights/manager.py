"""LED device manager for MohuanLED Bluetooth control."""

from __future__ import annotations

import asyncio
import colorsys
import logging
import os
from typing import TYPE_CHECKING

from bleak import BleakClient
from bleak.exc import BleakError
from dotenv import load_dotenv

from .commands import (
    LEDCommand,
    LEDDeviceInfo,
    build_color_command,
    validate_brightness,
    validate_rgb_value,
)
from .exceptions import (
    LEDCommandError,
    LEDConnectionError,
    LEDNotFoundError,
    LEDUUIDError,
)
from .scanner import Scanner

if TYPE_CHECKING:
    from collections.abc import Sequence

LOGGER = logging.getLogger(__name__)
load_dotenv()

LED_MAC_ADDRESS = os.getenv("LED_MAC_ADDRESS")
LED_UUID = os.getenv("LED_UUID")


class BJLEDInstance:
    """
    Controller class for MohuanLED Bluetooth LED devices.

    This class provides methods to control LED devices via Bluetooth Low Energy (BLE),
    including turning on/off, setting colors, and running various lighting effects.

    Attributes:
        mac: The MAC address of the LED device
        uuid: The UUID of the GATT characteristic for writing commands

    Example:
        async with BJLEDInstance() as led:
            await led.turn_on()
            await led.set_color_to_rgb(255, 0, 0)  # Red
            await led.rainbow_cycle(5.0)
            await led.turn_off()
    """

    def __init__(
        self,
        address: str | None = None,
        uuid: str | None = None,
        reset: bool = False,
        delay: int = 120,
    ) -> None:
        """
        Initialize the LED controller.

        Args:
            address: MAC address of the LED device. If None, will auto-discover.
            uuid: UUID of the GATT characteristic. If None, will auto-discover.
            reset: Whether to reset the device on connection.
            delay: Connection timeout delay in seconds.
        """
        self._mac = address or LED_MAC_ADDRESS
        self._uuid = uuid or LED_UUID
        self._reset = reset
        self._delay = delay
        self._client: BleakClient | None = None
        self._is_on: bool | None = None
        self._rgb_color: tuple[int, int, int] | None = None
        self._brightness: int = LEDDeviceInfo.DEFAULT_BRIGHTNESS
        self._effect: str | None = None
        self._effect_speed: int = 0x64
        self._color_mode: str = "RGB"
        self._scanner = Scanner()
        self._running_task: asyncio.Task[None] | None = None

    async def __aenter__(self) -> BJLEDInstance:
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Async context manager exit with cleanup."""
        await self.stop_effect()
        await self._disconnect()

    @property
    def mac(self) -> str | None:
        """Get the MAC address of the connected device."""
        return self._mac

    @property
    def uuid(self) -> str | None:
        """Get the UUID of the GATT characteristic."""
        return self._uuid

    @property
    def is_connected(self) -> bool:
        """Check if currently connected to the LED device."""
        return self._client is not None and self._client.is_connected

    @property
    def is_on(self) -> bool | None:
        """Get the current power state of the LED (None if unknown)."""
        return self._is_on

    @property
    def current_color(self) -> tuple[int, int, int] | None:
        """Get the current RGB color (None if unknown)."""
        return self._rgb_color

    async def initialize(self) -> None:
        """
        Initialize the LED device connection.

        If MAC address or UUID are not provided, this method will scan for
        available devices and attempt to find a compatible one.

        Raises:
            LEDNotFoundError: If no LED device is found during scanning.
            LEDUUIDError: If no compatible UUID is found for the device.
        """
        if not self._mac or not self._uuid:
            LOGGER.info("MAC or UUID not provided. Searching for LED...")
            self._mac, uuids = await self._scanner.run()
            if not self._mac:
                raise LEDNotFoundError()
            if uuids:
                await self._test_uuids(uuids)
            if not self._uuid:
                raise LEDUUIDError()

        LOGGER.info(f"Initialized LED with MAC: {self._mac} and UUID: {self._uuid}")

    async def _test_uuids(self, uuids: Sequence[str]) -> None:
        """
        Test a list of UUIDs to find one that works with the device.

        Args:
            uuids: List of UUID strings to test.
        """
        for uuid in uuids:
            try:
                self._uuid = uuid
                await self._ensure_connected()
                await self._write(LEDCommand.TURN_ON.value)
                await self._write(LEDCommand.TURN_OFF.value)
                LOGGER.info(f"Found compatible UUID: {uuid}")
                return
            except BleakError as e:
                LOGGER.debug(f"UUID {uuid} not compatible: {e}")
                await self._disconnect()
        self._uuid = None

    async def _ensure_connected(self, retries: int = 3) -> None:
        """
        Ensure connection to the LED device with retry logic.

        Args:
            retries: Number of connection attempts before giving up.

        Raises:
            LEDConnectionError: If MAC address or UUID is not set, or connection fails.
        """
        from bleak import BleakScanner

        if not self._mac or not self._uuid:
            raise LEDConnectionError("MAC address or UUID is not set", self._mac)

        if self._client and self._client.is_connected:
            return

        last_error: BleakError | None = None
        for attempt in range(retries):
            LOGGER.debug(f"Connecting to LED with MAC: {self._mac} (attempt {attempt + 1}/{retries})")
            try:
                # On Windows, we need to scan first to "wake up" the device
                LOGGER.debug("Scanning for device...")
                device = await BleakScanner.find_device_by_address(self._mac, timeout=5.0)
                if device:
                    LOGGER.debug(f"Found device: {device.name}")
                    self._client = BleakClient(device, timeout=20.0)
                else:
                    # Try direct connection anyway
                    LOGGER.debug("Device not found in scan, trying direct connection...")
                    self._client = BleakClient(self._mac, timeout=20.0)

                await self._client.connect()
                LOGGER.debug(f"Connected to LED at {self._mac}")
                return
            except BleakError as e:
                last_error = e
                LOGGER.warning(f"Connection attempt {attempt + 1} failed: {e}")
                # Clean up failed client
                if self._client:
                    try:
                        await self._client.disconnect()
                    except Exception:
                        pass
                    self._client = None
                # Wait before retry
                if attempt < retries - 1:
                    await asyncio.sleep(2.0)

        raise LEDConnectionError(f"Failed to connect after {retries} attempts: {last_error}", self._mac)

    async def _disconnect(self) -> None:
        """Disconnect from the LED device."""
        if self._client and self._client.is_connected:
            try:
                await self._client.disconnect()
                LOGGER.debug(f"Disconnected from LED at {self._mac}")
            except BleakError as e:
                LOGGER.warning(f"Error during disconnect: {e}")
            finally:
                self._client = None

    async def _write(self, data: bytearray, retry_on_failure: bool = True) -> None:
        """
        Write data to the LED device.

        Args:
            data: The bytearray command to send.
            retry_on_failure: If True, will reconnect and retry once on write failure.

        Raises:
            LEDCommandError: If the write operation fails.
        """
        await self._ensure_connected()
        # After _ensure_connected, _client and _uuid are guaranteed to be set
        assert self._client is not None
        assert self._uuid is not None
        try:
            await self._client.write_gatt_char(self._uuid, data, response=False)
            LOGGER.debug(f"Command {data.hex()} sent to LED at {self._mac}")
        except BleakError as e:
            if retry_on_failure:
                LOGGER.warning(f"Write failed, attempting reconnect: {e}")
                # Force disconnect and reconnect
                await self._disconnect()
                await self._ensure_connected()
                # Retry write without retry flag to avoid infinite loop
                await self._write(data, retry_on_failure=False)
            else:
                raise LEDCommandError(f"Failed to write command: {e}", bytes(data)) from e

    async def turn_on(self) -> None:
        """
        Turn on the LED device.

        Raises:
            LEDConnectionError: If not connected and connection fails.
            LEDCommandError: If the command fails to send.
        """
        await self._write(LEDCommand.TURN_ON.value)
        self._is_on = True
        LOGGER.info(f"LED at {self._mac} turned on")

    async def turn_off(self) -> None:
        """
        Turn off the LED device.

        Raises:
            LEDConnectionError: If not connected and connection fails.
            LEDCommandError: If the command fails to send.
        """
        await self._write(LEDCommand.TURN_OFF.value)
        self._is_on = False
        LOGGER.info(f"LED at {self._mac} turned off")

    async def set_color_to_rgb(
        self,
        red: int,
        green: int,
        blue: int,
        brightness: int | None = None,
    ) -> None:
        """
        Set the LED to a specific RGB color.

        Args:
            red: Red color value (0-255).
            green: Green color value (0-255).
            blue: Blue color value (0-255).
            brightness: Optional brightness value (0-255). Uses current brightness if not specified.

        Raises:
            ValueError: If any color or brightness value is outside the valid range.
            LEDCommandError: If the command fails to send.
        """
        red = validate_rgb_value(red, "Red")
        green = validate_rgb_value(green, "Green")
        blue = validate_rgb_value(blue, "Blue")

        if brightness is None:
            brightness = self._brightness
        else:
            brightness = validate_brightness(brightness)
            self._brightness = brightness

        # Apply brightness scaling
        red = int(red * brightness / 255)
        green = int(green * brightness / 255)
        blue = int(blue * brightness / 255)

        rgb_packet = build_color_command(red, green, blue)
        await self._write(rgb_packet)
        self._rgb_color = (red, green, blue)
        LOGGER.info(f"LED at {self._mac} set to RGB color: {self._rgb_color}")

    async def fade_to_color(
        self,
        start_color: tuple[int, int, int],
        end_color: tuple[int, int, int],
        duration: float,
    ) -> None:
        """
        Fade smoothly from one color to another.

        Args:
            start_color: Starting RGB color tuple.
            end_color: Ending RGB color tuple.
            duration: Duration of the fade in seconds.
        """
        steps = 100
        delay = duration / steps

        r1, g1, b1 = start_color
        r2, g2, b2 = end_color

        for step in range(steps + 1):
            red = int(r1 + (r2 - r1) * step / steps)
            green = int(g1 + (g2 - g1) * step / steps)
            blue = int(b1 + (b2 - b1) * step / steps)

            await self.set_color_to_rgb(red, green, blue)
            await asyncio.sleep(delay)

        LOGGER.info(f"LED at {self._mac} faded to color: {self._rgb_color}")

    async def fade_between_colors(
        self,
        colors: Sequence[tuple[int, int, int]],
        duration_per_color: float,
    ) -> None:
        """
        Fade smoothly between multiple colors.

        Args:
            colors: List of RGB color tuples to fade through.
            duration_per_color: Duration of each fade transition in seconds.
        """
        for i in range(len(colors) - 1):
            start_color = colors[i]
            end_color = colors[i + 1]
            await self.fade_to_color(start_color, end_color, duration_per_color)

        LOGGER.info(f"Completed fade between {len(colors)} colors.")

    async def wave_effect(
        self,
        colors: Sequence[tuple[int, int, int]],
        duration_per_wave: float,
    ) -> None:
        """
        Create a wave effect transitioning between multiple colors.

        Args:
            colors: List of RGB color tuples for the wave.
            duration_per_wave: Duration of each wave transition in seconds.
        """
        steps = len(colors) - 1

        for i in range(steps):
            start_color = colors[i]
            end_color = colors[i + 1]
            await self.fade_to_color(start_color, end_color, duration_per_wave)

        LOGGER.info("Completed wave effect.")

    async def rainbow_cycle(self, duration_per_color: float) -> None:
        """
        Run a rainbow color cycle animation.

        Args:
            duration_per_color: Total duration for one complete rainbow cycle in seconds.
        """
        steps = 360
        delay = duration_per_color / steps

        for hue in range(steps):
            r, g, b = [int(c * 255) for c in colorsys.hsv_to_rgb(hue / 360, 1.0, 1.0)]
            await self.set_color_to_rgb(r, g, b)
            await asyncio.sleep(delay)

        LOGGER.info("Completed rainbow cycle.")

    async def breathing_light(self, color: tuple[int, int, int], duration: float) -> None:
        """
        Create a breathing light effect with pulsing brightness.

        Args:
            color: RGB color tuple for the breathing effect.
            duration: Total duration of one breath cycle in seconds.
        """
        steps = 100
        delay = duration / (steps * 2)

        r, g, b = color
        # Fade in
        for step in range(steps):
            brightness = int((step / steps) * 255)
            await self.set_color_to_rgb(r, g, b, brightness)
            await asyncio.sleep(delay)

        # Fade out
        for step in range(steps, 0, -1):
            brightness = int((step / steps) * 255)
            await self.set_color_to_rgb(r, g, b, brightness)
            await asyncio.sleep(delay)

        LOGGER.info(f"Completed breathing effect with color {color}")

    async def strobe_light(
        self,
        color: tuple[int, int, int],
        duration: float,
        flashes: int,
    ) -> None:
        """
        Create a strobe light effect with rapid flashing.

        Args:
            color: RGB color tuple for the strobe.
            duration: Total duration of the strobe effect in seconds.
            flashes: Number of flashes during the duration.
        """
        r, g, b = color
        delay = duration / (flashes * 2)

        for _ in range(flashes):
            await self.set_color_to_rgb(r, g, b)
            await asyncio.sleep(delay)
            await self.turn_off()
            await asyncio.sleep(delay)

        LOGGER.info(f"Completed strobe effect with color {color} and {flashes} flashes.")

    async def color_cycle(
        self,
        colors: Sequence[tuple[int, int, int]],
        duration_per_color: float,
    ) -> None:
        """
        Continuously cycle through a list of colors.

        This method runs indefinitely until stop_effect() is called.

        Args:
            colors: List of RGB color tuples to cycle through.
            duration_per_color: Duration for each color transition in seconds.
        """
        try:
            while True:
                await self.fade_between_colors(colors, duration_per_color)
        except asyncio.CancelledError:
            LOGGER.info("Color cycle cancelled.")
            raise

    def start_color_cycle(
        self,
        colors: Sequence[tuple[int, int, int]],
        duration_per_color: float,
    ) -> asyncio.Task[None]:
        """
        Start a background color cycle task.

        Args:
            colors: List of RGB color tuples to cycle through.
            duration_per_color: Duration for each color transition in seconds.

        Returns:
            The asyncio Task running the color cycle.
        """
        self.stop_effect_sync()
        self._running_task = asyncio.create_task(
            self.color_cycle(colors, duration_per_color)
        )
        return self._running_task

    async def stop_effect(self) -> None:
        """Stop any currently running effect."""
        if self._running_task and not self._running_task.done():
            self._running_task.cancel()
            try:
                await self._running_task
            except asyncio.CancelledError:
                pass
            self._running_task = None
            LOGGER.info("Stopped running effect.")

    def stop_effect_sync(self) -> None:
        """Synchronously cancel any running effect (non-blocking)."""
        if self._running_task and not self._running_task.done():
            self._running_task.cancel()
            self._running_task = None
