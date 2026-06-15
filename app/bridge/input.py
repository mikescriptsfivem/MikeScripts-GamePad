"""Reading the physical HOTAS via pygame/SDL.

pygame opens the device through its joystick (DirectInput) backend, which
exposes every raw axis a HOTAS has — stick X/Y, throttle, rudder, sliders —
instead of the squashed XInput view. That's what lets us re-map them freely.
"""

from __future__ import annotations

import pygame

_initialized = False


def _ensure_init() -> None:
    """Initialise pygame once. The video subsystem must be up on Windows for
    SDL to receive joystick state, but no window is ever shown."""
    global _initialized
    if not _initialized:
        pygame.init()
        pygame.joystick.init()
        _initialized = True


def list_devices() -> list[dict]:
    _ensure_init()
    devices = []
    for i in range(pygame.joystick.get_count()):
        js = pygame.joystick.Joystick(i)
        js.init()
        devices.append(
            {
                "index": i,
                "name": js.get_name(),
                "axes": js.get_numaxes(),
                "buttons": js.get_numbuttons(),
                "hats": js.get_numhats(),
            }
        )
    return devices


def find_device_by_name(substr: str) -> int | None:
    _ensure_init()
    substr = substr.lower()
    for i in range(pygame.joystick.get_count()):
        js = pygame.joystick.Joystick(i)
        js.init()
        if substr in js.get_name().lower():
            return i
    return None


class JoystickInput:
    """A single opened HOTAS/joystick device."""

    def __init__(self, index: int = 0) -> None:
        _ensure_init()
        count = pygame.joystick.get_count()
        if count == 0:
            raise RuntimeError(
                "No joystick / HOTAS detected. Plug it in (and turn the Hotas One "
                "to PC/Xbox mode), then try again."
            )
        if not 0 <= index < count:
            raise RuntimeError(
                f"Device index {index} out of range — found {count} device(s). "
                f"Run `python run.py list` to see them."
            )
        self.index = index
        self.js = pygame.joystick.Joystick(index)
        self.js.init()

    @property
    def name(self) -> str:
        return self.js.get_name()

    @property
    def num_axes(self) -> int:
        return self.js.get_numaxes()

    @property
    def num_buttons(self) -> int:
        return self.js.get_numbuttons()

    @property
    def num_hats(self) -> int:
        return self.js.get_numhats()

    def poll(self) -> tuple[list[float], list[bool], list[tuple[int, int]]]:
        """Read the current state. Must be called every loop iteration."""
        pygame.event.pump()
        axes = [self.js.get_axis(i) for i in range(self.js.get_numaxes())]
        buttons = [bool(self.js.get_button(i)) for i in range(self.js.get_numbuttons())]
        hats = [self.js.get_hat(i) for i in range(self.js.get_numhats())]
        return axes, buttons, hats
