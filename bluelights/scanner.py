"""Bluetooth device scanner for MohuanLED devices."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError

from .commands import LEDDeviceInfo

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice

LOGGER = logging.getLogger(__name__)


class Scanner:
    """
    Scanner for discovering MohuanLED Bluetooth devices.

    This class provides methods to scan for BLE devices matching the
    MohuanLED naming pattern and retrieve their characteristic UUIDs.

    Example:
        scanner = Scanner()
        mac_address, uuids = await scanner.run()
        if mac_address:
            print(f"Found device at {mac_address}")
    """

    async def scan_led(self) -> tuple[str | None, BLEDevice | None]:
        """
        Scan for MohuanLED devices.

        Returns:
            A tuple of (MAC address, BLEDevice) if found, or (None, None) if not.
        """
        try:
            devices = await BleakScanner.discover()
        except BleakError as e:
            LOGGER.error(f"Failed to scan for devices: {e}")
            return None, None

        for device in devices:
            # Safety check for device.name being None
            if device.name and LEDDeviceInfo.DEVICE_NAME_PREFIX in device.name:
                LOGGER.info(f"Found LED: {device.name} with MAC: {device.address}")

                # Safety check for metadata (metadata is a runtime attribute)
                metadata = getattr(device, "metadata", None)
                if metadata and "uuids" in metadata:
                    LOGGER.debug(f"Device UUIDs from metadata: {metadata['uuids']}")

                return device.address, device

        LOGGER.info("No MohuanLED device found during scan.")
        return None, None

    async def scan_uuids(self, address: str) -> list[str]:
        """
        Retrieve characteristic UUIDs from a device.

        Args:
            address: The MAC address of the device to scan.

        Returns:
            A list of characteristic UUID strings.
        """
        uuid_list: list[str] = []

        try:
            async with BleakClient(address) as client:
                services = client.services
                if services is None:
                    LOGGER.warning(f"No services found for device at {address}")
                    return uuid_list

                for service in services:
                    LOGGER.debug(f"Service UUID: {service.uuid}")
                    for char in service.characteristics:
                        LOGGER.debug(f"  Characteristic UUID: {char.uuid}")
                        uuid_list.append(char.uuid)

        except BleakError as e:
            LOGGER.error(f"Failed to scan UUIDs for {address}: {e}")

        return uuid_list

    async def run(self) -> tuple[str | None, list[str]]:
        """
        Run a complete device discovery process.

        This method scans for MohuanLED devices and retrieves their
        characteristic UUIDs if a device is found.

        Returns:
            A tuple of (MAC address, list of UUIDs). If no device is found,
            returns (None, []).
        """
        mac_address, device = await self.scan_led()

        if mac_address:
            LOGGER.info(f"Scanning UUIDs for device at {mac_address}...")
            uuids = await self.scan_uuids(mac_address)
            LOGGER.info(f"Found {len(uuids)} characteristic UUIDs.")
            return mac_address, uuids

        return None, []
