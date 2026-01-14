"""Example usage of the BlueLights library."""

import asyncio
import logging

from bluelights import BJLEDInstance, LEDNotFoundError, LEDUUIDError

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


async def main() -> None:
    """Demonstrate basic LED control functionality."""
    try:
        # Using context manager for automatic cleanup
        async with BJLEDInstance() as led:
            await led.turn_on()
            await led.set_color_to_rgb(255, 0, 0)  # Red
            await asyncio.sleep(2)

            await led.set_color_to_rgb(0, 255, 0)  # Green
            await asyncio.sleep(2)

            await led.set_color_to_rgb(0, 0, 255)  # Blue
            await asyncio.sleep(2)

            await led.turn_off()

    except LEDNotFoundError as e:
        print(f"LED not found: {e}")
    except LEDUUIDError as e:
        print(f"UUID error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
