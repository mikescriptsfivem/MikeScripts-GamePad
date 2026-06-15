"""Interactive axis calibration.

You move each flight control in turn; this detects which physical axis it is,
which direction it travels, and (for the throttle) its real idle->full range.
That removes all guesswork about the device's axis numbering — the cause of
"rudder does nothing" (wrong/no axis) and "forward & reverse are flipped"
(throttle captured idle->full, so more = accelerate no matter the raw sign).

Only ``axes`` and ``axis_buttons`` are rewritten; buttons/hats/comments are kept.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from .bind import _resolve_device
from .input import JoystickInput

MIN_DELTA = 0.35  # how far an axis must move to count as "the one you moved"


def _settle_and_read(src: JoystickInput, frames: int = 6) -> list[float]:
    """Poll a few times so SDL state is current, then return axis values."""
    vals: list[float] = []
    for _ in range(frames):
        vals, _, _ = src.poll()
        time.sleep(1 / 120)
    return vals


def _pick_axis(rest: list[float], moved: list[float], exclude: set[int]) -> int | None:
    """Index of the axis that moved the most between the two readings."""
    best, best_delta = None, 0.0
    for i in range(min(len(rest), len(moved))):
        if i in exclude:
            continue
        d = abs(moved[i] - rest[i])
        if d > best_delta:
            best, best_delta = i, d
    if best is None or best_delta < MIN_DELTA:
        return None
    return best


def _invert_for(rest_val: float, moved_val: float, desired_sign: float) -> bool:
    """True if the axis must be inverted so the moved direction == desired_sign."""
    move_sign = 1.0 if (moved_val - rest_val) >= 0 else -1.0
    return move_sign != desired_sign


def _capture(src: JoystickInput, exclude: set[int], rest_text: str, move_text: str):
    """Guide one capture; return (index, rest_val, moved_val) or None."""
    input(f"    1) {rest_text}, then press ENTER...")
    rest = _settle_and_read(src)
    input(f"    2) {move_text}, then press ENTER...")
    moved = _settle_and_read(src)
    idx = _pick_axis(rest, moved, exclude)
    if idx is None:
        return None
    return idx, rest[idx], moved[idx]


def calibrate(profile_path: str, device_index: int | None = None) -> None:
    path = Path(profile_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    idx = _resolve_device(data, device_index)
    src = JoystickInput(idx)

    print(f"\nCalibrating axes for: {src.name}  (device {idx})")
    print(f"This device reports {src.num_axes} axes.\n")
    print("You'll move each control so I can learn which axis it is.\n")

    used: set[int] = set()
    axes_out: list[dict] = []
    axis_buttons_out: list[dict] = []

    # --- Roll (stick left/right -> LEFT_X, right = positive) ---
    print("[1/4] ROLL  - bank left/right")
    cap = _capture(src, used, "Center the stick", "Push the stick fully RIGHT and hold")
    if cap:
        i, rest, moved = cap
        used.add(i)
        axes_out.append({
            "source": i, "target": "LEFT_X",
            "invert": _invert_for(rest, moved, +1), "deadzone": 0.06, "expo": 0.2,
            "comment": "roll",
        })
        print(f"    -> axis [{i}] = roll\n")
    else:
        print("    (no movement detected — skipped)\n")

    # --- Pitch (stick fwd/back -> LEFT_Y, back = climb = negative) ---
    print("[2/4] PITCH - nose up/down")
    cap = _capture(src, used, "Center the stick", "Pull the stick fully BACK (toward you) and hold")
    if cap:
        i, rest, moved = cap
        used.add(i)
        axes_out.append({
            "source": i, "target": "LEFT_Y",
            "invert": _invert_for(rest, moved, -1), "deadzone": 0.06, "expo": 0.2,
            "comment": "pitch (back = climb; flip invert if it feels reversed)",
        })
        print(f"    -> axis [{i}] = pitch\n")
    else:
        print("    (no movement detected — skipped)\n")

    # --- Throttle (-> RT, idle..full captured so forward always = accelerate) ---
    print("[3/4] THROTTLE - accelerate / ascend")
    cap = _capture(src, used, "Pull the throttle ALL THE WAY BACK (idle)",
                   "Push the throttle fully FORWARD and hold")
    if cap:
        i, rest, moved = cap
        used.add(i)
        axes_out.append({
            "source": i, "target": "RT",
            "min": round(rest, 4), "max": round(moved, 4), "deadzone": 0.03,
            "comment": "throttle: idle->full mapped to right trigger",
        })
        print(f"    -> axis [{i}] = throttle (idle {rest:+.2f}, full {moved:+.2f})\n")
    else:
        print("    (no movement detected — skipped)\n")

    # --- Rudder / yaw (twist axis -> LB/RB). Must self-centre, else it's a
    #     throttle/slider that would jam yaw on forever. ---
    print("[4/4] RUDDER / YAW - twist the stick (FIRST unlock the twist & use 5/8")
    print("      axis mode; skip with ENTER if your stick has no usable twist)")
    cap = _capture(src, used, "Center the rudder / twist",
                   "Twist the stick fully RIGHT (or press right rudder) and hold")
    if cap:
        i, rest, moved = cap
        input("    3) Now LET GO so it springs back to centre, then press ENTER...")
        released = _settle_and_read(src)
        recentred = i < len(released) and abs(released[i] - rest) <= 0.3
        if not recentred:
            print(f"    Axis [{i}] does NOT spring back to centre — that's a throttle/")
            print("    slider, not a rudder. Skipping it (this is what caused the")
            print("    constant-turn bug). Set yaw on two BUTTONS in the next step.\n")
        else:
            used.add(i)
            axis_buttons_out.append({
                "source": i, "negative": "LB", "positive": "RB", "threshold": 0.5,
                "invert": _invert_for(rest, moved, +1), "comment": "rudder twist -> yaw",
            })
            print(f"    -> axis [{i}] = rudder/yaw (LB/RB)\n")
    else:
        print("    No self-centring rudder axis found. Set yaw as two buttons (LB / RB)")
        print("    in the button step instead.\n")

    data["axes"] = axes_out
    data["axis_buttons"] = axis_buttons_out
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Saved {len(axes_out)} axis mapping(s) to {profile_path}")
    print("Next: run the button wizard to map your buttons  ->  bind.bat")
