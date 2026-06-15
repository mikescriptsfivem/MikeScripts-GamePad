"""The virtual Xbox 360 controller, driven through ViGEmBus via `vgamepad`.

A fresh PadState is built every frame and applied wholesale, so nothing
"sticks" between frames. `vgamepad` is imported lazily so that `list` and
`monitor` work even before the ViGEmBus driver is installed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .curves import clamp, clamp01


@dataclass
class PadState:
    """Desired state of the virtual pad for a single frame."""

    lx: float = 0.0
    ly: float = 0.0
    rx: float = 0.0
    ry: float = 0.0
    lt: float = 0.0
    rt: float = 0.0
    buttons: set[str] = field(default_factory=set)
    dpad: tuple[int, int] = (0, 0)  # (x, y) each in {-1, 0, 1}


class VirtualPad:
    def __init__(self) -> None:
        try:
            import vgamepad as vg
        except Exception as exc:  # pragma: no cover - import/driver error path
            raise RuntimeError(
                "Could not load vgamepad. Install it with `pip install vgamepad` "
                "and make sure the ViGEmBus driver is installed "
                "(https://github.com/ViGEm/ViGEmBus/releases)."
            ) from exc

        try:
            self._vg = vg
            self.gp = vg.VX360Gamepad()
        except Exception as exc:  # pragma: no cover - driver-not-running path
            raise RuntimeError(
                "Created vgamepad but couldn't open a virtual controller. The "
                "ViGEmBus driver is probably not installed or not running. "
                "Install it from https://github.com/ViGEm/ViGEmBus/releases and reboot."
            ) from exc

        B = vg.XUSB_BUTTON
        self._buttons = {
            "A": B.XUSB_GAMEPAD_A,
            "B": B.XUSB_GAMEPAD_B,
            "X": B.XUSB_GAMEPAD_X,
            "Y": B.XUSB_GAMEPAD_Y,
            "LB": B.XUSB_GAMEPAD_LEFT_SHOULDER,
            "RB": B.XUSB_GAMEPAD_RIGHT_SHOULDER,
            "LS": B.XUSB_GAMEPAD_LEFT_THUMB,
            "RS": B.XUSB_GAMEPAD_RIGHT_THUMB,
            "BACK": B.XUSB_GAMEPAD_BACK,
            "START": B.XUSB_GAMEPAD_START,
            "GUIDE": B.XUSB_GAMEPAD_GUIDE,
            "DPAD_UP": B.XUSB_GAMEPAD_DPAD_UP,
            "DPAD_DOWN": B.XUSB_GAMEPAD_DPAD_DOWN,
            "DPAD_LEFT": B.XUSB_GAMEPAD_DPAD_LEFT,
            "DPAD_RIGHT": B.XUSB_GAMEPAD_DPAD_RIGHT,
        }

    def apply(self, st: PadState) -> None:
        gp = self.gp
        gp.reset()
        gp.left_joystick_float(clamp(st.lx), clamp(st.ly))
        gp.right_joystick_float(clamp(st.rx), clamp(st.ry))
        gp.left_trigger_float(clamp01(st.lt))
        gp.right_trigger_float(clamp01(st.rt))

        for name in st.buttons:
            btn = self._buttons.get(name)
            if btn is not None:
                gp.press_button(btn)

        dx, dy = st.dpad
        if dy > 0:
            gp.press_button(self._buttons["DPAD_UP"])
        if dy < 0:
            gp.press_button(self._buttons["DPAD_DOWN"])
        if dx < 0:
            gp.press_button(self._buttons["DPAD_LEFT"])
        if dx > 0:
            gp.press_button(self._buttons["DPAD_RIGHT"])

        gp.update()

    def reset(self) -> None:
        self.gp.reset()
        self.gp.update()
