"""PyQt6-based GUI application for controlling MohuanLED devices."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from bleak.exc import BleakError
from dotenv import load_dotenv
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)
from qasync import QEventLoop, asyncSlot

from bluelights.exceptions import (
    BlueLightsError,
    LEDCommandError,
    LEDConnectionError,
    LEDNotFoundError,
    LEDOperationCancelledError,
    LEDTimeoutError,
)
from bluelights.manager import BJLEDInstance as Instance

LOGGER = logging.getLogger(__name__)
load_dotenv()

LED_MAC_ADDRESS = os.getenv("LED_MAC_ADDRESS")
LED_UUID = os.getenv("LED_UUID")

# Get the project root directory for resource loading
PROJECT_ROOT = Path(__file__).parent.parent

# Dark mode stylesheet
DARK_STYLE = """
QWidget {
    background-color: #1e1e1e;
    color: #ffffff;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 10pt;
}

QGroupBox {
    border: 1px solid #3d3d3d;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 10px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: #888888;
}

QPushButton {
    background-color: #2d2d2d;
    border: 1px solid #3d3d3d;
    border-radius: 4px;
    padding: 8px 16px;
    min-height: 20px;
}

QPushButton:hover {
    background-color: #3d3d3d;
    border-color: #4d4d4d;
}

QPushButton:pressed {
    background-color: #1d1d1d;
}

QPushButton#onButton {
    background-color: #1a472a;
    border-color: #2d5a3d;
}

QPushButton#onButton:hover {
    background-color: #2d5a3d;
}

QPushButton#offButton {
    background-color: #4a1a1a;
    border-color: #5a2d2d;
}

QPushButton#offButton:hover {
    background-color: #5a2d2d;
}

QPushButton#strobeButton {
    background-color: #4a3a1a;
    border-color: #5a4a2d;
}

QPushButton#strobeButton:hover {
    background-color: #5a4a2d;
}

QSlider::groove:horizontal {
    border: 1px solid #3d3d3d;
    height: 8px;
    border-radius: 4px;
    background: #2d2d2d;
}

QSlider::handle:horizontal {
    background: #888888;
    border: 1px solid #666666;
    width: 16px;
    margin: -4px 0;
    border-radius: 8px;
}

QSlider::handle:horizontal:hover {
    background: #aaaaaa;
}

QSlider#redSlider::groove:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #2d1a1a, stop:1 #8b0000);
}

QSlider#greenSlider::groove:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #1a2d1a, stop:1 #006400);
}

QSlider#blueSlider::groove:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #1a1a2d, stop:1 #00008b);
}

QSpinBox {
    background-color: #2d2d2d;
    border: 1px solid #3d3d3d;
    border-radius: 4px;
    padding: 2px 5px;
    min-width: 50px;
}

QSpinBox::up-button, QSpinBox::down-button {
    background-color: #3d3d3d;
    border: none;
    width: 16px;
}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #4d4d4d;
}

QFrame#colorPreview {
    border: 2px solid #3d3d3d;
    border-radius: 4px;
    min-height: 40px;
}

QLabel {
    color: #cccccc;
}

QLabel#titleLabel {
    font-size: 14pt;
    font-weight: bold;
    color: #ffffff;
}
"""


class LEDController(QWidget):
    """
    Main GUI window for controlling LED devices.

    Provides controls for:
    - Power on/off
    - RGB color adjustment via sliders
    - Rainbow cycle animation
    - Color fade effects
    """

    # Debounce delay for color slider updates (milliseconds)
    COLOR_UPDATE_DEBOUNCE_MS: int = 50

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
        self._color_update_task: asyncio.Task[None] | None = None
        self._color_update_timer: QTimer | None = None
        self._operation_in_progress: bool = False
        self.init_ui()
        self.init_tray_icon()
        self._setup_color_debounce()

    def init_ui(self) -> None:
        """Initialize the user interface components."""
        self.setWindowTitle("LED Controller")
        self.setMinimumWidth(320)
        self.setStyleSheet(DARK_STYLE)

        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Connection group
        connection_group = QGroupBox("Connection")
        connection_layout = QVBoxLayout()
        self.reconnect_button = QPushButton("Reconnect")
        self.reconnect_button.clicked.connect(self.on_reconnect_clicked)
        connection_layout.addWidget(self.reconnect_button)
        connection_group.setLayout(connection_layout)
        main_layout.addWidget(connection_group)

        # Power group
        power_group = QGroupBox("Power")
        power_layout = QHBoxLayout()
        self.on_button = QPushButton("Turn ON")
        self.on_button.setObjectName("onButton")
        self.on_button.clicked.connect(self.on_turn_on_clicked)
        self.off_button = QPushButton("Turn OFF")
        self.off_button.setObjectName("offButton")
        self.off_button.clicked.connect(self.on_turn_off_clicked)
        power_layout.addWidget(self.on_button)
        power_layout.addWidget(self.off_button)
        power_group.setLayout(power_layout)
        main_layout.addWidget(power_group)

        # Color group
        color_group = QGroupBox("Color")
        color_layout = QVBoxLayout()

        # Red slider row
        red_row = QHBoxLayout()
        red_label = QLabel("R")
        red_label.setFixedWidth(20)
        self.red_slider = QSlider(Qt.Orientation.Horizontal)
        self.red_slider.setObjectName("redSlider")
        self.red_slider.setMaximum(255)
        self.red_slider.setValue(255)
        self.red_spinbox = QSpinBox()
        self.red_spinbox.setMaximum(255)
        self.red_spinbox.setValue(255)
        self.red_slider.valueChanged.connect(self.red_spinbox.setValue)
        self.red_slider.valueChanged.connect(self.update_color)
        self.red_spinbox.valueChanged.connect(self.red_slider.setValue)
        red_row.addWidget(red_label)
        red_row.addWidget(self.red_slider)
        red_row.addWidget(self.red_spinbox)
        color_layout.addLayout(red_row)

        # Green slider row
        green_row = QHBoxLayout()
        green_label = QLabel("G")
        green_label.setFixedWidth(20)
        self.green_slider = QSlider(Qt.Orientation.Horizontal)
        self.green_slider.setObjectName("greenSlider")
        self.green_slider.setMaximum(255)
        self.green_slider.setValue(0)
        self.green_spinbox = QSpinBox()
        self.green_spinbox.setMaximum(255)
        self.green_spinbox.setValue(0)
        self.green_slider.valueChanged.connect(self.green_spinbox.setValue)
        self.green_slider.valueChanged.connect(self.update_color)
        self.green_spinbox.valueChanged.connect(self.green_slider.setValue)
        green_row.addWidget(green_label)
        green_row.addWidget(self.green_slider)
        green_row.addWidget(self.green_spinbox)
        color_layout.addLayout(green_row)

        # Blue slider row
        blue_row = QHBoxLayout()
        blue_label = QLabel("B")
        blue_label.setFixedWidth(20)
        self.blue_slider = QSlider(Qt.Orientation.Horizontal)
        self.blue_slider.setObjectName("blueSlider")
        self.blue_slider.setMaximum(255)
        self.blue_slider.setValue(0)
        self.blue_spinbox = QSpinBox()
        self.blue_spinbox.setMaximum(255)
        self.blue_spinbox.setValue(0)
        self.blue_slider.valueChanged.connect(self.blue_spinbox.setValue)
        self.blue_slider.valueChanged.connect(self.update_color)
        self.blue_spinbox.valueChanged.connect(self.blue_slider.setValue)
        blue_row.addWidget(blue_label)
        blue_row.addWidget(self.blue_slider)
        blue_row.addWidget(self.blue_spinbox)
        color_layout.addLayout(blue_row)

        # Color preview
        preview_row = QHBoxLayout()
        preview_label = QLabel("Preview")
        self.color_preview = QFrame()
        self.color_preview.setObjectName("colorPreview")
        self.color_preview.setStyleSheet("background-color: #ff0000;")
        preview_row.addWidget(preview_label)
        preview_row.addWidget(self.color_preview, 1)
        color_layout.addLayout(preview_row)

        color_group.setLayout(color_layout)
        main_layout.addWidget(color_group)

        # Effects group
        effects_group = QGroupBox("Effects")
        effects_layout = QHBoxLayout()
        self.rainbow_button = QPushButton("Rainbow")
        self.rainbow_button.clicked.connect(self.on_rainbow_clicked)
        self.fade_button = QPushButton("Fade")
        self.fade_button.clicked.connect(self.on_fade_clicked)
        self.strobe_button = QPushButton("Strobe")
        self.strobe_button.setObjectName("strobeButton")
        self.strobe_button.clicked.connect(self.on_strobe_clicked)
        effects_layout.addWidget(self.rainbow_button)
        effects_layout.addWidget(self.fade_button)
        effects_layout.addWidget(self.strobe_button)
        effects_group.setLayout(effects_layout)
        main_layout.addWidget(effects_group)

        main_layout.addStretch()
        self.setLayout(main_layout)

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

    def _setup_color_debounce(self) -> None:
        """Set up the debounce timer for color updates."""
        self._color_update_timer = QTimer()
        self._color_update_timer.setSingleShot(True)
        self._color_update_timer.timeout.connect(self._execute_color_update)

    def _set_buttons_enabled(self, enabled: bool) -> None:
        """Enable or disable all action buttons."""
        self.reconnect_button.setEnabled(enabled)
        self.on_button.setEnabled(enabled)
        self.off_button.setEnabled(enabled)
        self.rainbow_button.setEnabled(enabled)
        self.fade_button.setEnabled(enabled)
        self.strobe_button.setEnabled(enabled)

    def _start_operation(self) -> bool:
        """
        Try to start an operation. Returns True if operation can proceed.

        If another operation is in progress, returns False.
        """
        if self._operation_in_progress:
            return False
        self._operation_in_progress = True
        self._set_buttons_enabled(False)
        return True

    def _end_operation(self) -> None:
        """Mark the current operation as complete and re-enable buttons."""
        self._operation_in_progress = False
        self._set_buttons_enabled(True)

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
            await self.led_instance.connect()
            LOGGER.info("LED initialized and connected successfully")
        except LEDOperationCancelledError as e:
            LOGGER.warning(f"LED initialization cancelled: {e}")
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
            QMessageBox.warning(self, "LED Connection Failed", detailed_msg)
        except LEDNotFoundError as e:
            LOGGER.warning(f"LED not found: {e}")
            detailed_msg = (
                "Could not find LED device.\n\n"
                "Possible causes:\n"
                "• The LED device is not powered on\n"
                "• The LED device is too far away\n"
                "• Bluetooth is turned off\n\n"
                "Solution:\n"
                "• Make sure the LED device is powered on\n"
                "• Move the LED device closer to the computer\n"
                "• Check Bluetooth settings\n"
                "• Try the 'Reconnect' button"
            )
            QMessageBox.warning(self, "LED Connection Failed", detailed_msg)
        except LEDConnectionError as e:
            LOGGER.warning(f"LED connection failed: {e}")
            detailed_msg = (
                f"Could not connect to LED device: {e}\n\n"
                "You can try to reconnect using the 'Reconnect' button."
            )
            QMessageBox.warning(self, "LED Connection Failed", detailed_msg)
        except BlueLightsError as e:
            LOGGER.warning(f"LED initialization failed: {e}")
            QMessageBox.warning(
                self,
                "LED Connection Failed",
                f"Could not connect to LED device: {e}\n\n"
                "You can try to reconnect using the 'Reconnect' button.",
            )

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt method name
        """Handle window close by exiting the application."""
        self.exit_application()
        event.accept()

    def exit_application(self) -> None:
        """Exit the application with a visual indicator."""
        asyncio.run_coroutine_threadsafe(self._exit_application(), self._loop)

    async def _exit_application(self) -> None:
        """Coroutine to handle shutdown sequence."""
        try:
            # Visual feedback: red strobe effect
            await self.led_instance.strobe_light(color=(255, 0, 0), duration=2.0, flashes=5)
            await self.led_instance.turn_off()
            await self.led_instance.disconnect()
        except BlueLightsError as e:
            LOGGER.error(f"Error during exit: {e}")
        except BleakError as e:
            LOGGER.error(f"BLE error during exit: {e}")
        finally:
            QApplication.quit()

    async def reconnect(self) -> None:
        """Disconnect and reconnect to the LED device."""
        LOGGER.info("Reconnecting to LED...")
        try:
            # Disconnect first if connected
            if self.led_instance.is_connected:
                await self.led_instance.disconnect()
            # Try to ensure connection (will reconnect if needed)
            await self.led_instance.connect()
            LOGGER.info("Reconnected successfully!")
            QMessageBox.information(self, "Success", "Successfully reconnected to LED device!")
        except LEDNotFoundError:
            LOGGER.error("Reconnect failed: Device not found")
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
            QMessageBox.warning(self, "Reconnect Failed", detailed_msg)
        except LEDOperationCancelledError:
            LOGGER.error("Reconnect failed: Operation cancelled")
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
            QMessageBox.warning(self, "Reconnect Failed", detailed_msg)
        except LEDConnectionError as e:
            LOGGER.error(f"Reconnect failed: {e}")
            QMessageBox.warning(self, "Reconnect Failed", f"Reconnection failed: {e}")
        except BlueLightsError as e:
            LOGGER.error(f"Reconnect failed: {e}")
            QMessageBox.warning(self, "Reconnect Failed", f"Reconnection failed: {e}")

    async def turn_on_with_initial_color(self) -> None:
        """Turn on LEDs and set initial color based on slider values."""
        red = self.red_slider.value()
        green = self.green_slider.value()
        blue = self.blue_slider.value()

        # If all sliders are at 0, use default red color
        if red == 0 and green == 0 and blue == 0:
            red, green, blue = 255, 0, 0

        # Set color first, then turn on (some LEDs need color before turn on works)
        await self.led_instance.set_color_to_rgb(red, green, blue)
        await self.led_instance.turn_on()

    def update_color(self) -> None:
        """Update LED color when sliders change (debounced)."""
        # Update color preview immediately
        self._update_color_preview()
        # Restart the debounce timer - actual LED update happens after timer fires
        if self._color_update_timer:
            self._color_update_timer.start(self.COLOR_UPDATE_DEBOUNCE_MS)

    def _update_color_preview(self) -> None:
        """Update the color preview box to show current slider values."""
        red = self.red_slider.value()
        green = self.green_slider.value()
        blue = self.blue_slider.value()
        self.color_preview.setStyleSheet(f"background-color: rgb({red}, {green}, {blue});")

    def _execute_color_update(self) -> None:
        """Execute the actual color update after debounce delay."""
        # Cancel any pending color update task
        if self._color_update_task and not self._color_update_task.done():
            self._color_update_task.cancel()

        red = self.red_slider.value()
        green = self.green_slider.value()
        blue = self.blue_slider.value()

        async def _do_update() -> None:
            try:
                await self.led_instance.set_color_to_rgb(red, green, blue)
            except asyncio.CancelledError:
                pass  # Task was cancelled, this is expected
            except BlueLightsError as e:
                LOGGER.error(f"Update color error: {e}")
            except BleakError as e:
                LOGGER.error(f"BLE error updating color: {e}")

        self._color_update_task = asyncio.create_task(_do_update())

    @asyncSlot()
    async def on_reconnect_clicked(self) -> None:
        """Handle reconnect button click."""
        if not self._start_operation():
            return
        try:
            await self.reconnect()
        finally:
            self._end_operation()

    @asyncSlot()
    async def on_turn_on_clicked(self) -> None:
        """Handle turn on button click."""
        if not self._start_operation():
            return
        try:
            if not self.led_instance.is_connected:
                await self.led_instance.connect()
            await self.turn_on_with_initial_color()
        except LEDOperationCancelledError:
            LOGGER.error("Turn on failed: Operation cancelled")
            QMessageBox.warning(
                self,
                "Turn On Error",
                "Failed to turn on LED: Operation was cancelled.\n\n"
                "Make sure:\n"
                "• No other apps are connected to the LED\n"
                "• The LED device is powered on\n"
                "• Try using 'Reconnect' button first",
            )
        except BlueLightsError as e:
            LOGGER.error(f"Turn on error: {e}")
            QMessageBox.warning(self, "Turn On Error", f"Failed to turn on LED: {e}")
        finally:
            self._end_operation()

    @asyncSlot()
    async def on_turn_off_clicked(self) -> None:
        """Handle turn off button click."""
        if not self._start_operation():
            return
        try:
            if not self.led_instance.is_connected:
                await self.led_instance.connect()
            await self.led_instance.turn_off()
        except LEDOperationCancelledError:
            LOGGER.error("Turn off failed: Operation cancelled")
            QMessageBox.warning(
                self,
                "Turn Off Error",
                "Failed to turn off LED: Operation was cancelled.\n\n"
                "Make sure:\n"
                "• No other apps are connected to the LED\n"
                "• The LED device is powered on\n"
                "• Try using 'Reconnect' button first",
            )
        except BlueLightsError as e:
            LOGGER.error(f"Turn off error: {e}")
            QMessageBox.warning(self, "Turn Off Error", f"Failed to turn off LED: {e}")
        finally:
            self._end_operation()

    @asyncSlot()
    async def on_rainbow_clicked(self) -> None:
        """Handle rainbow cycle button click."""
        if not self._start_operation():
            return
        try:
            if not self.led_instance.is_connected:
                await self.led_instance.connect()
            await self.led_instance.rainbow_cycle(5.0)
        except LEDOperationCancelledError:
            LOGGER.error("Rainbow cycle failed: Operation cancelled")
            QMessageBox.warning(
                self,
                "Rainbow Cycle Error",
                "Failed to start rainbow cycle: Operation was cancelled.\n\n"
                "Make sure:\n"
                "• No other apps are connected to the LED\n"
                "• The LED device is powered on\n"
                "• Try using 'Reconnect' button first",
            )
        except BlueLightsError as e:
            LOGGER.error(f"Rainbow cycle error: {e}")
            QMessageBox.warning(self, "Rainbow Cycle Error", f"Failed to start rainbow cycle: {e}")
        finally:
            self._end_operation()

    @asyncSlot()
    async def on_fade_clicked(self) -> None:
        """Handle fade colors button click."""
        if not self._start_operation():
            return
        try:
            if not self.led_instance.is_connected:
                await self.led_instance.connect()
            await self.fade_colors()
        except LEDOperationCancelledError:
            LOGGER.error("Fade colors failed: Operation cancelled")
            QMessageBox.warning(
                self,
                "Fade Colors Error",
                "Failed to fade colors: Operation was cancelled.\n\n"
                "Make sure:\n"
                "• No other apps are connected to the LED\n"
                "• The LED device is powered on\n"
                "• Try using 'Reconnect' button first",
            )
        except BlueLightsError as e:
            LOGGER.error(f"Fade colors error: {e}")
            QMessageBox.warning(self, "Fade Colors Error", f"Failed to fade colors: {e}")
        finally:
            self._end_operation()

    async def fade_colors(self) -> None:
        """Execute fade effect from current color to red."""
        start_color = (
            self.red_slider.value(),
            self.green_slider.value(),
            self.blue_slider.value(),
        )
        end_color = (255, 0, 0)
        await self.led_instance.fade_to_color(start_color, end_color, 5.0)

    @asyncSlot()
    async def on_strobe_clicked(self) -> None:
        """Handle strobe button click."""
        if not self._start_operation():
            return
        try:
            if not self.led_instance.is_connected:
                await self.led_instance.connect()

            # Use current slider color, or white if all zeros
            red = self.red_slider.value()
            green = self.green_slider.value()
            blue = self.blue_slider.value()
            if red == 0 and green == 0 and blue == 0:
                red, green, blue = 255, 255, 255

            await self.led_instance.strobe_light(
                color=(red, green, blue),
                duration=2.0,
                flashes=10,
            )
        except LEDOperationCancelledError:
            LOGGER.error("Strobe failed: Operation cancelled")
            QMessageBox.warning(
                self,
                "Strobe Error",
                "Failed to start strobe: Operation was cancelled.\n\n"
                "Make sure:\n"
                "• No other apps are connected to the LED\n"
                "• The LED device is powered on\n"
                "• Try using 'Reconnect' button first",
            )
        except BlueLightsError as e:
            LOGGER.error(f"Strobe error: {e}")
            QMessageBox.warning(self, "Strobe Error", f"Failed to start strobe: {e}")
        finally:
            self._end_operation()


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
