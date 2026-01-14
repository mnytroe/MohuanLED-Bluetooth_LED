"""PyQt6-based GUI application for controlling MohuanLED devices."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMenu,
    QPushButton,
    QSlider,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)
from qasync import QEventLoop, asyncSlot

from bluelights.manager import BJLEDInstance as Instance

LOGGER = logging.getLogger(__name__)
load_dotenv()

LED_MAC_ADDRESS = os.getenv("LED_MAC_ADDRESS")
LED_UUID = os.getenv("LED_UUID")

# Get the project root directory for resource loading
PROJECT_ROOT = Path(__file__).parent.parent


class LEDController(QWidget):
    """
    Main GUI window for controlling LED devices.

    Provides controls for:
    - Power on/off
    - RGB color adjustment via sliders
    - Rainbow cycle animation
    - Color fade effects
    """

    def __init__(self, led_instance: Instance, loop: asyncio.AbstractEventLoop) -> None:
        """
        Initialize the LED controller GUI.

        Args:
            led_instance: The BJLEDInstance to control.
            loop: The asyncio event loop for async operations.
        """
        super().__init__()
        self.led_instance = led_instance
        self._loop = loop
        self.init_ui()
        self.init_tray_icon()

    def init_ui(self) -> None:
        """Initialize the user interface components."""
        self.setWindowTitle("LED Controller")
        layout = QVBoxLayout()

        # Reconnect button
        self.reconnect_button = QPushButton("Reconnect")
        self.reconnect_button.clicked.connect(self.on_reconnect_clicked)
        layout.addWidget(self.reconnect_button)

        # Power on button
        self.on_button = QPushButton("Turn ON")
        self.on_button.clicked.connect(self.on_turn_on_clicked)
        layout.addWidget(self.on_button)

        # Power off button
        self.off_button = QPushButton("Turn OFF")
        self.off_button.clicked.connect(self.on_turn_off_clicked)
        layout.addWidget(self.off_button)

        # Red color slider
        self.red_slider = QSlider(Qt.Orientation.Horizontal)
        self.red_slider.setMaximum(255)
        self.red_slider.setValue(0)
        self.red_slider.valueChanged.connect(self.update_color)
        layout.addWidget(QLabel("Red"))
        layout.addWidget(self.red_slider)

        # Green color slider
        self.green_slider = QSlider(Qt.Orientation.Horizontal)
        self.green_slider.setMaximum(255)
        self.green_slider.setValue(0)
        self.green_slider.valueChanged.connect(self.update_color)
        layout.addWidget(QLabel("Green"))
        layout.addWidget(self.green_slider)

        # Blue color slider
        self.blue_slider = QSlider(Qt.Orientation.Horizontal)
        self.blue_slider.setMaximum(255)
        self.blue_slider.setValue(0)
        self.blue_slider.valueChanged.connect(self.update_color)
        layout.addWidget(QLabel("Blue"))
        layout.addWidget(self.blue_slider)

        # Rainbow cycle button
        self.rainbow_button = QPushButton("Rainbow Cycle")
        self.rainbow_button.clicked.connect(self.on_rainbow_clicked)
        layout.addWidget(self.rainbow_button)

        # Fade colors button
        self.fade_button = QPushButton("Fade Colors")
        self.fade_button.clicked.connect(self.on_fade_clicked)
        layout.addWidget(self.fade_button)

        self.setLayout(layout)

    def init_tray_icon(self) -> None:
        """Initialize the system tray icon and menu."""
        # Try to load icon from resource directory, fallback to built-in icon
        icon_path = PROJECT_ROOT / "src" / "ico" / "avatar.jpg"
        if icon_path.exists():
            icon = QIcon(str(icon_path))
        else:
            # Use built-in Qt icon as fallback
            from PyQt6.QtWidgets import QStyle
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)

        self.tray_icon = QSystemTrayIcon(icon, parent=self)
        self.tray_icon.setToolTip("LED Controller")

        # Create context menu for tray icon
        self.tray_menu = QMenu()
        self.exit_action = QAction("Exit")
        self.exit_action.triggered.connect(self.exit_application)
        self.tray_menu.addAction(self.exit_action)

        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()

    def tray_icon_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """
        Handle tray icon activation events.

        Args:
            reason: The reason for activation (click type).
        """
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()

    def showEvent(self, event) -> None:  # noqa: N802 - Qt method name
        """Handle show event to initialize LED after GUI is shown."""
        super().showEvent(event)
        # Schedule LED initialization after event loop starts
        QTimer.singleShot(100, lambda: asyncio.create_task(self._init_led()))

    async def _init_led(self) -> None:
        """Initialize LED connection asynchronously."""
        try:
            await self.led_instance.initialize()
            await self.led_instance._ensure_connected()
            LOGGER.info("LED initialized and connected successfully")
        except Exception as e:
            LOGGER.warning(f"LED initialization failed: {e}. You can try to reconnect using the Reconnect button.")
            from PyQt6.QtWidgets import QMessageBox
            error_msg = str(e)
            # Check for specific error types
            if "WinError -2147023673" in error_msg or "avbrutt" in error_msg.lower():
                detailed_msg = (
                    "Could not connect to LED device: Operation was cancelled.\n\n"
                    "Possible causes:\n"
                    "• Another app (Mohuan app, Windows BLE Explorer, etc.) is connected\n"
                    "• The device is in use by another application\n"
                    "• Bluetooth connection timeout\n\n"
                    "Solution:\n"
                    "• Close other apps that might be connected to the LED\n"
                    "• Disconnect from other Bluetooth apps\n"
                    "• Make sure the LED device is powered on and nearby\n"
                    "• Try the 'Reconnect' button after closing other apps"
                )
            elif "connected" in error_msg.lower() or "already" in error_msg.lower() or "in use" in error_msg.lower():
                detailed_msg = (
                    f"Could not connect to LED device.\n\n"
                    f"Error: {error_msg}\n\n"
                    "Possible causes:\n"
                    "• Another app (Mohuan app, Windows BLE Explorer, etc.) is connected\n"
                    "• The device is in use by another application\n\n"
                    "Solution:\n"
                    "• Close other apps that might be connected to the LED\n"
                    "• Disconnect from other Bluetooth apps\n"
                    "• Try the 'Reconnect' button after closing other apps"
                )
            else:
                detailed_msg = (
                    f"Could not connect to LED device: {error_msg}\n\n"
                    "You can try to reconnect using the 'Reconnect' button."
                )
            QMessageBox.warning(
                self,
                "LED Connection Failed",
                detailed_msg,
            )

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt method name
        """Override closeEvent to minimize to tray instead of closing."""
        self.hide()
        event.ignore()

    def exit_application(self) -> None:
        """Exit the application with a visual indicator."""
        asyncio.run_coroutine_threadsafe(self._exit_application(), self._loop)

    async def _exit_application(self) -> None:
        """Coroutine to handle shutdown sequence."""
        try:
            # Visual feedback: red strobe effect
            await self.led_instance.strobe_light(color=(255, 0, 0), duration=2.0, flashes=5)
            await self.led_instance.turn_off()
            await self.led_instance._disconnect()
        except Exception as e:
            LOGGER.error(f"Error during exit: {e}")
        finally:
            QApplication.quit()

    async def reconnect(self) -> None:
        """Disconnect and reconnect to the LED device."""
        LOGGER.info("Reconnecting to LED...")
        from PyQt6.QtWidgets import QMessageBox
        try:
            # Disconnect first if connected
            if self.led_instance.is_connected:
                await self.led_instance._disconnect()
            # Try to ensure connection (will reconnect if needed)
            await self.led_instance._ensure_connected()
            LOGGER.info("Reconnected successfully!")
            QMessageBox.information(self, "Success", "Successfully reconnected to LED device!")
        except Exception as e:
            LOGGER.error(f"Reconnect failed: {e}")
            error_msg = str(e)
            if "not found" in error_msg.lower():
                detailed_msg = (
                    "Reconnection failed: Device not found.\n\n"
                    "Possible causes:\n"
                    "• The LED device is not powered on\n"
                    "• The LED device is too far away\n"
                    "• Bluetooth is turned off\n"
                    "• Another app is using the device\n\n"
                    "Solution:\n"
                    "• Make sure the LED device is powered on\n"
                    "• Move the LED device closer to the computer\n"
                    "• Check Bluetooth settings\n"
                    "• Close other apps that might be connected\n"
                    "• Wait a few seconds and try again"
                )
            elif "WinError -2147023673" in error_msg or "avbrutt" in error_msg.lower():
                detailed_msg = (
                    "Reconnection failed: Operation was cancelled.\n\n"
                    "Possible causes:\n"
                    "• Another app (Mohuan app, Windows BLE Explorer, etc.) is connected\n"
                    "• The device is in use by another application\n"
                    "• Bluetooth connection timeout\n\n"
                    "Solution:\n"
                    "• Close other apps that might be connected to the LED\n"
                    "• Disconnect from other Bluetooth apps\n"
                    "• Make sure the LED device is powered on and nearby\n"
                    "• Wait a few seconds and try again"
                )
            elif "connected" in error_msg.lower() or "already" in error_msg.lower() or "in use" in error_msg.lower():
                detailed_msg = (
                    f"Reconnection failed.\n\n"
                    f"Error: {error_msg}\n\n"
                    "The device may be connected to another app.\n"
                    "Please close other Bluetooth apps and try again."
                )
            else:
                detailed_msg = f"Reconnection failed: {error_msg}"
            QMessageBox.warning(self, "Reconnect Failed", detailed_msg)

    async def turn_on_with_initial_color(self) -> None:
        """Turn on LEDs and set initial color based on slider values."""
        await self.led_instance.turn_on()

        red = self.red_slider.value()
        green = self.green_slider.value()
        blue = self.blue_slider.value()

        # If all sliders are at 0, use default red color
        if red == 0 and green == 0 and blue == 0:
            red, green, blue = 255, 0, 0

        await self.led_instance.set_color_to_rgb(red, green, blue)

    def update_color(self) -> None:
        """Update LED color when sliders change."""
        red = self.red_slider.value()
        green = self.green_slider.value()
        blue = self.blue_slider.value()
        try:
            asyncio.create_task(self.led_instance.set_color_to_rgb(red, green, blue))
        except Exception as e:
            LOGGER.error(f"Update color error: {e}")

    @asyncSlot()
    async def on_reconnect_clicked(self) -> None:
        """Handle reconnect button click."""
        await self.reconnect()

    @asyncSlot()
    async def on_turn_on_clicked(self) -> None:
        """Handle turn on button click."""
        try:
            if not self.led_instance.is_connected:
                await self.led_instance._ensure_connected()
            await self.turn_on_with_initial_color()
        except Exception as e:
            LOGGER.error(f"Turn on error: {e}")
            from PyQt6.QtWidgets import QMessageBox
            error_msg = str(e)
            if "WinError -2147023673" in error_msg or "avbrutt" in error_msg.lower():
                detailed_msg = (
                    "Failed to turn on LED: Operation was cancelled.\n\n"
                    "Make sure:\n"
                    "• No other apps are connected to the LED\n"
                    "• The LED device is powered on\n"
                    "• Try using 'Reconnect' button first"
                )
            else:
                detailed_msg = f"Failed to turn on LED: {error_msg}"
            QMessageBox.warning(self, "Turn On Error", detailed_msg)

    @asyncSlot()
    async def on_turn_off_clicked(self) -> None:
        """Handle turn off button click."""
        try:
            if not self.led_instance.is_connected:
                await self.led_instance._ensure_connected()
            await self.led_instance.turn_off()
        except Exception as e:
            LOGGER.error(f"Turn off error: {e}")
            from PyQt6.QtWidgets import QMessageBox
            error_msg = str(e)
            if "WinError -2147023673" in error_msg or "avbrutt" in error_msg.lower():
                detailed_msg = (
                    "Failed to turn off LED: Operation was cancelled.\n\n"
                    "Make sure:\n"
                    "• No other apps are connected to the LED\n"
                    "• The LED device is powered on\n"
                    "• Try using 'Reconnect' button first"
                )
            else:
                detailed_msg = f"Failed to turn off LED: {error_msg}"
            QMessageBox.warning(self, "Turn Off Error", detailed_msg)

    @asyncSlot()
    async def on_rainbow_clicked(self) -> None:
        """Handle rainbow cycle button click."""
        try:
            if not self.led_instance.is_connected:
                await self.led_instance._ensure_connected()
            await self.led_instance.rainbow_cycle(5.0)
        except Exception as e:
            LOGGER.error(f"Rainbow cycle error: {e}")
            from PyQt6.QtWidgets import QMessageBox
            error_msg = str(e)
            if "WinError -2147023673" in error_msg or "avbrutt" in error_msg.lower():
                detailed_msg = (
                    "Failed to start rainbow cycle: Operation was cancelled.\n\n"
                    "Make sure:\n"
                    "• No other apps are connected to the LED\n"
                    "• The LED device is powered on\n"
                    "• Try using 'Reconnect' button first"
                )
            else:
                detailed_msg = f"Failed to start rainbow cycle: {error_msg}"
            QMessageBox.warning(self, "Rainbow Cycle Error", detailed_msg)

    @asyncSlot()
    async def on_fade_clicked(self) -> None:
        """Handle fade colors button click."""
        try:
            if not self.led_instance.is_connected:
                await self.led_instance._ensure_connected()
            await self.fade_colors()
        except Exception as e:
            LOGGER.error(f"Fade colors error: {e}")
            from PyQt6.QtWidgets import QMessageBox
            error_msg = str(e)
            if "WinError -2147023673" in error_msg or "avbrutt" in error_msg.lower():
                detailed_msg = (
                    "Failed to fade colors: Operation was cancelled.\n\n"
                    "Make sure:\n"
                    "• No other apps are connected to the LED\n"
                    "• The LED device is powered on\n"
                    "• Try using 'Reconnect' button first"
                )
            else:
                detailed_msg = f"Failed to fade colors: {error_msg}"
            QMessageBox.warning(self, "Fade Colors Error", detailed_msg)

    async def fade_colors(self) -> None:
        """Execute fade effect from current color to red."""
        start_color = (
            self.red_slider.value(),
            self.green_slider.value(),
            self.blue_slider.value(),
        )
        end_color = (255, 0, 0)
        await self.led_instance.fade_to_color(start_color, end_color, 5.0)


def main() -> None:
    """Main entry point for the GUI application."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    led_instance = Instance(address=LED_MAC_ADDRESS, uuid=LED_UUID)
    controller = LEDController(led_instance, loop)
    controller.show()

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
