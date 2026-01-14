"""PyQt6-based GUI application for controlling MohuanLED devices."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from PyQt6.QtCore import Qt
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
from qasync import QEventLoop

from bluelights.manager import BJLEDInstance as Instance

LOGGER = logging.getLogger(__name__)
load_dotenv()

LED_MAC_ADDRESS = os.getenv("LED_MAC_ADDRESS")
LED_UUID = os.getenv("LED_UUID")

# Get the directory containing this file for resource loading
RESOURCE_DIR = Path(__file__).parent


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
        self.reconnect_button.clicked.connect(
            lambda: asyncio.create_task(self.reconnect())
        )
        layout.addWidget(self.reconnect_button)

        # Power on button
        self.on_button = QPushButton("Turn ON")
        self.on_button.clicked.connect(
            lambda: asyncio.create_task(self.turn_on_with_initial_color())
        )
        layout.addWidget(self.on_button)

        # Power off button
        self.off_button = QPushButton("Turn OFF")
        self.off_button.clicked.connect(
            lambda: asyncio.create_task(self.led_instance.turn_off())
        )
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
        self.rainbow_button.clicked.connect(
            lambda: asyncio.create_task(self.led_instance.rainbow_cycle(5.0))
        )
        layout.addWidget(self.rainbow_button)

        # Fade colors button
        self.fade_button = QPushButton("Fade Colors")
        self.fade_button.clicked.connect(lambda: asyncio.create_task(self.fade_colors()))
        layout.addWidget(self.fade_button)

        self.setLayout(layout)

    def init_tray_icon(self) -> None:
        """Initialize the system tray icon and menu."""
        # Try to load icon from resource directory, fallback to empty icon
        icon_path = RESOURCE_DIR / "avatar.jpg"
        if icon_path.exists():
            icon = QIcon(str(icon_path))
        else:
            LOGGER.warning(f"Tray icon not found at {icon_path}")
            icon = QIcon()

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
        try:
            await self.led_instance._disconnect()
            await self.led_instance._ensure_connected()
            LOGGER.info("Reconnected successfully!")
        except Exception as e:
            LOGGER.error(f"Reconnect failed: {e}")

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
        asyncio.create_task(self.led_instance.set_color_to_rgb(red, green, blue))

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
