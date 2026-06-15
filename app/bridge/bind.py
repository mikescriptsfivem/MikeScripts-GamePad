"""Interactive button binding.

Walks through each gamepad output, you press the HOTAS button you want for it,
and the chosen mapping is written back to the profile. This sidesteps having to
know which physical button is which pygame index — you just press it.

Only the ``buttons`` section of the profile is rewritten; axes, hats and any
comments are preserved.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from .input import JoystickInput, find_device_by_name

try:
    import msvcrt  # Windows console keypresses (ENTER/Q while we poll the stick)
except ImportError:  # pragma: no cover - non-Windows
    msvcrt = None


# (pad target, human description) in roughly flight-useful order.
# Your Hotas One has no twist rudder, so YAW lives on LB/RB here -- bind those
# two to whatever buttons you want to steer the nose left/right with.
BIND_TARGETS = [
    ("LB", "YAW LEFT  (LB)  - rudder / turn nose left   <-- your rudder!"),
    ("RB", "YAW RIGHT (RB)  - rudder / turn nose right  <-- your rudder!"),
    ("LT_FULL", "LT  - aim / brake / heli descend"),
    ("RT_FULL", "RT  - fire weapon / boost   (note: overlaps your throttle axis)"),
    ("A", "A   - jump / accept / handbrake"),
    ("B", "B   - cancel / horn"),
    ("X", "X   - reload / vehicle brake"),
    ("Y", "Y   - enter / exit vehicle, change view"),
    ("LS", "LS  - left-stick click (sprint / crouch)"),
    ("RS", "RS  - right-stick click (zoom / stealth)"),
    ("START", "Start - pause menu"),
    ("BACK", "Back  - phone / map"),
    ("DPAD_UP", "D-pad Up"),
    ("DPAD_DOWN", "D-pad Down"),
    ("DPAD_LEFT", "D-pad Left"),
    ("DPAD_RIGHT", "D-pad Right"),
]


def _resolve_device(data: dict, device_index: int | None) -> int:
    if device_index is not None:
        return device_index
    if data.get("device_index") is not None:
        return int(data["device_index"])
    if data.get("device_name_contains"):
        found = find_device_by_name(data["device_name_contains"])
        if found is not None:
            return found
    return 0


def _wait_for_button(src: JoystickInput):
    """Block until a button is newly pressed.

    Returns the button index, ``None`` if the user pressed ENTER (skip), or the
    string ``"QUIT"`` if they pressed Q/Esc.
    """
    _, baseline, _ = src.poll()
    prev = list(baseline)
    while True:
        if msvcrt and msvcrt.kbhit():
            ch = msvcrt.getch()
            if ch in (b"\r", b"\n"):
                return None
            if ch in (b"q", b"Q", b"\x1b"):
                return "QUIT"
        _, buttons, _ = src.poll()
        for i, pressed in enumerate(buttons):
            if pressed and (i >= len(prev) or not prev[i]):
                return i
        prev = list(buttons)
        time.sleep(1 / 120)


def _wait_release(src: JoystickInput) -> None:
    """Wait until no button is held, so one press isn't reused for the next prompt."""
    while True:
        _, buttons, _ = src.poll()
        if not any(buttons):
            return
        time.sleep(1 / 120)


def _save_bindings(path: str | Path, bindings: list[dict]) -> dict:
    """Rewrite only the ``buttons`` array, preserving the rest of the file."""
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    data["buttons"] = [{"source": b["source"], "target": b["target"]} for b in bindings]
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def bind(profile_path: str, device_index: int | None = None) -> None:
    path = Path(profile_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    idx = _resolve_device(data, device_index)
    src = JoystickInput(idx)

    print(f"\nBinding buttons for: {src.name}  (device {idx})")
    print(f"Profile: {data.get('name', profile_path)}")
    print(f"This device reports {src.num_buttons} buttons.\n")
    print("For each action below: PRESS the HOTAS button you want for it.")
    print("  ENTER = skip (leave unbound)    Q = finish and save\n")

    bindings: list[dict] = []
    for target, desc in BIND_TARGETS:
        print(f">>> {desc}")
        print("    waiting for a button...  (ENTER=skip, Q=finish)", flush=True)
        result = _wait_for_button(src)
        if result == "QUIT":
            print("    finishing.\n")
            break
        if result is None:
            print("    skipped.\n")
            continue
        print(f"    OK: physical button [{result}]  ->  {target}\n")
        bindings.append({"source": result, "target": target})
        _wait_release(src)

    if not bindings:
        print("No buttons bound — profile left unchanged.")
        return

    _save_bindings(path, bindings)
    print(f"Saved {len(bindings)} button binding(s) to {profile_path}")
    print("Start the bridge to use them:  run.bat   (or  python run.py run)")
