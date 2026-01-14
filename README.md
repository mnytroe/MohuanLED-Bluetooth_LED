# MohuanLED Bluetooth Control

BJ_LED_M is a Python library designed to control MohuanLED brand lights via Bluetooth, directly from your laptop or PC (you'll need a Bluetooth adapter if it's not built-in). This library allows you to perform simple actions like turning the lights on/off, changing colors, and applying animations or reactions to external events. It also includes a PyQt6-based GUI for more intuitive control over the lights.

## Usage

The library is fully asynchronous and supports async context managers for automatic cleanup. Here's an example using the recommended context manager approach:

```python
from bluelights import BJLEDInstance
import asyncio

ADDRESS = '64:11:a8:00:8b:a6'                      # Example address
UUID = '0000ee02-0000-1000-2000-00805f9b34fb'      # Example UUID

async def main():
    async with BJLEDInstance(address=ADDRESS, uuid=UUID) as led:
        await led.turn_on()
        await led.set_color_to_rgb(255, 0, 0)      # Change color to red (RGB)
        await asyncio.sleep(5)                     # Wait 5 seconds
        await led.turn_off()

asyncio.run(main())
```

For dynamic connection with auto-discovery, use `.initialize()` or the context manager without arguments:

```python
from bluelights import BJLEDInstance, LEDNotFoundError
import asyncio

async def main():
    try:
        async with BJLEDInstance() as led:         # Auto-scans for 'BJ_LED_M' devices
            await led.turn_on()
            await led.set_color_to_rgb(255, 0, 0)
            await asyncio.sleep(5)
            await led.turn_off()
    except LEDNotFoundError:
        print("No LED device found. Make sure it's powered on.")

asyncio.run(main())
```

> [!WARNING]
> If you do not provide a MAC Address or a UUID, the code WILL require `initialize()` or use the context manager.

## Features

- Control MohuanLED lights via Bluetooth (BLE)
- Turn the LEDs on and off
- Change colors across the full RGB spectrum
- RGB value validation (0-255)
- Apply effects like:
  - Color fade
  - Color strobe
  - Breathing effect between colors
  - Rainbow cycle
  - Wave effect
  - Continuous color cycling (with cancellation support)
- Graphical user interface (GUI) using PyQt6
- Automatic retry logic for Windows BLE compatibility
- Custom exceptions for better error handling
- Async context manager support for automatic cleanup
- Type hints throughout the codebase

## Installation

### Requirements
- Python 3.10 or higher
- Built-in or external Bluetooth adapter
- MohuanLED lights

Install dependencies:

```bash
pip install -r requirements.txt
```

For development (includes testing and linting tools):

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

Or install directly from the repository:

```bash
git clone https://github.com/Walkercito/MohuanLED-Bluetooth_LED
cd MohuanLED-Bluetooth_LED
pip install .
```

## Applying Effects

You can add various effects to the lights, such as `rainbow_cycle`, `wave_effect`, or `strobe_light`:

```python
# Apply the 'rainbow_cycle' effect
await led.rainbow_cycle(duration_per_color=5.0)

# Apply the 'strobe_light' effect with 10 flashes
await led.strobe_light(color=(255, 255, 255), duration=5.0, flashes=10)

# Start a continuous color cycle (runs in background)
task = led.start_color_cycle(
    colors=[(255, 0, 0), (0, 255, 0), (0, 0, 255)],
    duration_per_color=2.0
)

# Stop the effect when done
await led.stop_effect()
```

## GUI Control

The library provides a graphical user interface (GUI) built with PyQt6 to visually control the lights.

To launch the GUI:

```bash
python -m gui.app
```

The GUI includes:
- **Reconnect** button - Re-scan and connect to the LED device
- **Turn ON/OFF** buttons - Power control
- **RGB sliders** - Adjust red, green, and blue values
- **Rainbow Cycle** - Run rainbow animation
- **Fade Colors** - Fade from current color to red
- **System tray** - Minimize to tray instead of closing

## Configuration

You can configure your setup using a `.env` file to store your MohuanLED light's MAC address and UUID.

Create a `.env` file in the project directory:

```bash
LED_MAC_ADDRESS=xx:xx:xx:xx:xx:xx
LED_UUID=0000xxxx-0000-1000-8000-00805f9b34fb
```

The library will automatically load these values when you instantiate the LEDs.

## Error Handling

The library provides custom exceptions for better error handling:

```python
from bluelights import (
    BJLEDInstance,
    LEDNotFoundError,
    LEDConnectionError,
    LEDCommandError,
    LEDUUIDError,
)

try:
    async with BJLEDInstance() as led:
        await led.turn_on()
except LEDNotFoundError:
    print("No LED device found")
except LEDConnectionError as e:
    print(f"Connection failed: {e}")
except LEDCommandError as e:
    print(f"Command failed: {e}")
```

## Development

If you want to contribute or modify the project:

Clone the repository:

```bash
git clone https://github.com/Walkercito/MohuanLED-Bluetooth_LED
```

Install dependencies (including dev tools):

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

Run linting:

```bash
python -m ruff check bluelights/ gui/
```

Run type checking:

```bash
python -m mypy bluelights/ --ignore-missing-imports
```

## License

This project is licensed under the MIT License. See the LICENSE file for more details.

## Acknowledgments

- [Bleak](https://github.com/hbldh/bleak): For Bluetooth Low Energy (BLE) device control
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/): For creating the graphical interface
- [qasync](https://github.com/CabbageDevelopment/qasync): For handling asynchronous processes in PyQt6
- [python-dotenv](https://github.com/theskumar/python-dotenv): For auto-loading environment variables
