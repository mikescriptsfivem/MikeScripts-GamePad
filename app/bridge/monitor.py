"""Live, in-place view of every axis/button/hat.

Use it to discover which physical control is which pygame index, watch the
min/max each axis actually reaches (for calibration), and confirm deadzones.
Needs no ViGEmBus driver — it only reads the HOTAS.
"""

from __future__ import annotations

import os
import time

from .input import JoystickInput


def _bar(v: float, width: int = 21) -> str:
    half = width // 2
    pos = int(round(v * half))
    cells = []
    for k in range(-half, half + 1):
        if k == 0:
            cells.append("|")
        elif pos >= 0 and 0 < k <= pos:
            cells.append("#")
        elif pos < 0 and pos <= k < 0:
            cells.append("#")
        else:
            cells.append("-")
    return "".join(cells)


def monitor(device_index: int = 0) -> None:
    os.system("")  # enable ANSI escape handling on legacy Windows consoles
    src = JoystickInput(device_index)
    n = src.num_axes
    mins = [0.0] * n
    maxs = [0.0] * n

    print(f"Monitoring: {src.name}  (device {device_index})")
    print("Move every axis fully and press each button to learn its index.")
    print("Copy the axis numbers into your profile JSON. Ctrl+C to exit.\n")

    first = True
    try:
        while True:
            axes, buttons, hats = src.poll()
            lines = [f"{'AXES':<7}{'value':>8} {'min':>7} {'max':>7}   bar (centre = | )"]
            for i, a in enumerate(axes):
                mins[i] = min(mins[i], a)
                maxs[i] = max(maxs[i], a)
                lines.append(
                    f"  [{i:>2}] {a:>8.3f} {mins[i]:>7.2f} {maxs[i]:>7.2f}   {_bar(a)}"
                )
            pressed = [str(i) for i, b in enumerate(buttons) if b]
            lines.append("")
            lines.append(f"BUTTONS down: {', '.join(pressed) if pressed else '(none)'}")
            lines.append(f"HATS: {hats if hats else '(none)'}")

            if not first:
                print(f"\033[{len(lines)}A", end="")  # cursor up to overwrite block
            first = False
            print("\n".join(lines))
            time.sleep(1 / 60)
    except KeyboardInterrupt:
        print("\nDone.")
