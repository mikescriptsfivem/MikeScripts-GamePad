"""Expandable profile library + the catalogue of mappable outputs.

The GUI and CLI both read profiles from a folder of JSON files. Anyone can add
support for a new HOTAS or a new game by dropping a ``*.json`` file into
``profiles/`` — no code changes needed. These helpers discover those files and
convert between the GUI's selection widgets and a :class:`Profile`.

To add a brand-new *output* (e.g. a DualShock button) you only extend the lists
below and teach :mod:`bridge.output` about it; everything else is data-driven.
"""

from __future__ import annotations

import json
from pathlib import Path

from .profile import AxisButtonsMap, AxisMap, ButtonMap, Profile

YAW_THRESHOLD = 0.35  # how far the twist must move (from rest) to count as a turn

# Recognised manufacturers, matched against the device's reported name.
# Order matters (first hit wins); add more freely.
KNOWN_BRANDS = [
    ("thrustmaster", "Thrustmaster"),
    ("guillemot", "Thrustmaster"),
    ("hotas", "Thrustmaster"),
    ("t.16000", "Thrustmaster"),
    ("tca ", "Thrustmaster"),
    ("logitech", "Logitech"),
    ("logi ", "Logitech"),
    ("saitek", "Logitech / Saitek"),
    ("x52", "Logitech / Saitek"),
    ("x56", "Logitech / Saitek"),
    ("turtle beach", "Turtle Beach"),
    ("velocityone", "Turtle Beach"),
    ("vkb", "VKB"),
    ("gunfighter", "VKB"),
    ("virpil", "VIRPIL"),
    ("vpc", "VIRPIL"),
    ("honeycomb", "Honeycomb"),
    ("alpha flight", "Honeycomb"),
    ("bravo throttle", "Honeycomb"),
    ("ch products", "CH Products"),
    ("winwing", "WINWING"),
    ("moza", "MOZA"),
    ("8bitdo", "8BitDo"),
    ("xbox", "Xbox / Microsoft"),
    ("microsoft", "Xbox / Microsoft"),
    ("wireless controller", "PlayStation"),
    ("dualsense", "PlayStation"),
    ("sony", "PlayStation"),
]


def identify_brand(device_name: str | None) -> str:
    """Friendly manufacturer name for a device, or 'Generic'."""
    name = (device_name or "").lower()
    for key, label in KNOWN_BRANDS:
        if key in name:
            return label
    return "Generic"

# Analog outputs on the virtual pad, with friendly labels for the GUI.
AXIS_OUTPUTS = [
    ("LEFT_X", "Roll  -  left stick X"),
    ("LEFT_Y", "Pitch -  left stick Y"),
    ("RIGHT_X", "Look X - right stick X"),
    ("RIGHT_Y", "Look Y - right stick Y"),
    ("RT", "Throttle - right trigger (gas only)"),
    ("LT", "Brake - left trigger"),
    ("RT_LT_SPLIT", "Throttle+reverse - 1 lever: push=gas, pull=brake/reverse"),
]

# Digital outputs. *_FULL slam a trigger fully via a button.
BUTTON_OUTPUTS = [
    ("LB", "Yaw LEFT  (rudder)"),
    ("RB", "Yaw RIGHT (rudder)"),
    ("RT_FULL", "Fire / boost  (RT)"),
    ("LT_FULL", "Brake / descend (LT)"),
    ("A", "A  -  jump / accept"),
    ("B", "B  -  cancel / horn"),
    ("X", "X  -  reload / brake"),
    ("Y", "Y  -  enter-exit / view"),
    ("LS", "L-stick click"),
    ("RS", "R-stick click"),
    ("START", "Start / pause"),
    ("BACK", "Back / map"),
    ("DPAD_UP", "D-pad up"),
    ("DPAD_DOWN", "D-pad down"),
    ("DPAD_LEFT", "D-pad left"),
    ("DPAD_RIGHT", "D-pad right"),
]

_STICK_TARGETS = {"LEFT_X", "LEFT_Y", "RIGHT_X", "RIGHT_Y"}
TRIGGER_TARGETS = {"LT", "RT"}
# axes whose 0..1 range should be auto-calibrated from observed travel
AUTORANGE_TARGETS = {"LT", "RT", "RT_LT_SPLIT"}


def discover_profiles(profiles_dir: str | Path) -> list[dict]:
    """Every readable ``*.json`` profile in a folder, as {path, name, device}."""
    found = []
    for path in sorted(Path(profiles_dir).glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        found.append(
            {
                "path": str(path),
                "name": data.get("name", path.stem),
                "device": data.get("device_name_contains", ""),
            }
        )
    return found


def build_profile(
    name: str,
    device_hint: str,
    axis_sel: dict[str, tuple[int | None, bool]],
    button_sel: dict[str, int | None],
    yaw: tuple[int | None, bool] = (None, False),
    update_rate_hz: int = 120,
) -> Profile:
    """Turn GUI selections into a Profile.

    ``axis_sel``  : target -> (source axis index or None, invert)
    ``button_sel``: target -> source button index or None
    ``yaw``       : (twist axis index or None, invert) -> LB/RB yaw
    """
    axes = []
    for target, (src, invert) in axis_sel.items():
        if src is None:
            continue
        if target in _STICK_TARGETS:
            deadzone, expo = 0.06, 0.2
        elif target == "RT_LT_SPLIT":
            deadzone, expo = 0.10, 0.0  # wider neutral so the lever rests cleanly
        else:
            deadzone, expo = 0.03, 0.0
        axes.append(
            AxisMap(source=src, target=target, invert=invert, deadzone=deadzone, expo=expo)
        )
    buttons = [
        ButtonMap(source=src, target=target)
        for target, src in button_sel.items()
        if src is not None
    ]
    axis_buttons = []
    yaw_src, yaw_inv = yaw
    if yaw_src is not None:
        axis_buttons.append(
            AxisButtonsMap(
                source=yaw_src, negative="LB", positive="RB",
                threshold=YAW_THRESHOLD, invert=yaw_inv,
            )
        )
    return Profile(
        name=name,
        device_name_contains=device_hint or None,
        update_rate_hz=update_rate_hz,
        axes=axes,
        buttons=buttons,
        axis_buttons=axis_buttons,
    )


def selections_from_profile(profile: Profile):
    """Inverse of build_profile: pre-fill the GUI widgets from a saved profile."""
    axis_sel: dict[str, tuple[int | None, bool]] = {t: (None, False) for t, _ in AXIS_OUTPUTS}
    for am in profile.axes:
        if am.target in axis_sel:
            axis_sel[am.target] = (am.source, am.invert)
    button_sel: dict[str, int | None] = {t: None for t, _ in BUTTON_OUTPUTS}
    for bm in profile.buttons:
        if bm.target in button_sel:
            button_sel[bm.target] = bm.source
    yaw: tuple[int | None, bool] = (None, False)
    for ab in profile.axis_buttons:
        if ab.negative == "LB" and ab.positive == "RB":
            yaw = (ab.source, ab.invert)
            break
    return axis_sel, button_sel, yaw
